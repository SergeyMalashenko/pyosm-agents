"""Geometry preparation, Overpass decoding, and exact parcel relationships."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from pyproj import CRS, Transformer
from shapely import make_valid
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
    mapping,
    shape,
)
from shapely.geometry.base import BaseGeometry
from shapely.ops import polygonize, transform, unary_union

from .schemas import GeometrySummary, SpatialRelationData

AREA_EPSILON_M2 = 1e-6
LENGTH_EPSILON_M = 1e-6
DEFAULT_MAX_POLYGON_AREA_KM2 = 500.0

AREA_TAG_KEYS = frozenset(
    {
        "building",
        "building:part",
        "landuse",
        "leisure",
        "amenity",
        "shop",
        "tourism",
        "historic",
        "healthcare",
    }
)
NON_AREA_NATURAL_VALUES = frozenset({"coastline", "cliff", "ridge", "tree_row"})


class GeometryUnavailableError(ValueError):
    """Raised when a supplied geometry cannot be used for polygon analysis."""


class GeometryLimitError(ValueError):
    """Raised when a contour is too large for the bounded public-service tool."""


def _polygon_parts(geometry: BaseGeometry) -> Iterable[Polygon]:
    if isinstance(geometry, Polygon):
        yield geometry
    elif isinstance(geometry, MultiPolygon):
        yield from geometry.geoms
    elif isinstance(geometry, GeometryCollection):
        for part in geometry.geoms:
            yield from _polygon_parts(part)


def _line_parts(geometry: BaseGeometry) -> Iterable[LineString]:
    if isinstance(geometry, LineString):
        yield geometry
    elif isinstance(geometry, MultiLineString):
        yield from geometry.geoms
    elif isinstance(geometry, GeometryCollection):
        for part in geometry.geoms:
            yield from _line_parts(part)


def _point_parts(geometry: BaseGeometry) -> Iterable[Point]:
    if isinstance(geometry, Point):
        yield geometry
    elif isinstance(geometry, MultiPoint):
        yield from geometry.geoms
    elif isinstance(geometry, GeometryCollection):
        for part in geometry.geoms:
            yield from _point_parts(part)


def _polygonal(geometry: BaseGeometry) -> BaseGeometry:
    polygons = list(_polygon_parts(geometry))
    if not polygons:
        raise GeometryUnavailableError("Geometry must be a Polygon or MultiPolygon")
    result = unary_union(polygons)
    if result.is_empty:
        raise GeometryUnavailableError("Polygon geometry is empty")
    return result


def prepare_polygon_geometry(value: dict[str, Any] | BaseGeometry) -> BaseGeometry:
    """Return a valid non-empty WGS84 polygonal geometry."""

    try:
        geometry = value if isinstance(value, BaseGeometry) else shape(value)
    except (TypeError, ValueError, KeyError) as exc:
        raise GeometryUnavailableError("Invalid GeoJSON polygon geometry") from exc
    if geometry.is_empty:
        raise GeometryUnavailableError("Polygon geometry is empty")
    if not geometry.is_valid:
        geometry = make_valid(geometry)
    geometry = _polygonal(geometry)
    min_x, min_y, max_x, max_y = geometry.bounds
    if min_x < -180 or max_x > 180 or min_y < -90 or max_y > 90:
        raise GeometryUnavailableError("Polygon coordinates must use WGS84 lon/lat")
    return geometry


def _metric_transformers(
    geometry: BaseGeometry,
) -> tuple[Transformer, Transformer]:
    centroid = geometry.centroid
    local_equal_area = CRS.from_proj4(
        "+proj=laea "
        f"+lat_0={centroid.y} +lon_0={centroid.x} "
        "+datum=WGS84 +units=m +no_defs"
    )
    return (
        Transformer.from_crs("EPSG:4326", local_equal_area, always_xy=True),
        Transformer.from_crs(local_equal_area, "EPSG:4326", always_xy=True),
    )


def geometry_summary(geometry: BaseGeometry) -> GeometrySummary:
    """Build a compact WGS84 summary with geodesically useful metric area."""

    forward, _ = _metric_transformers(geometry)
    projected = transform(forward.transform, geometry)
    centroid = geometry.centroid
    return GeometrySummary(
        type=geometry.geom_type,
        bbox=tuple(float(value) for value in geometry.bounds),
        centroid=(float(centroid.x), float(centroid.y)),
        area_m2=round(float(projected.area), 3),
    )


def validate_query_contour(
    geometry: BaseGeometry,
    *,
    max_area_km2: float = DEFAULT_MAX_POLYGON_AREA_KM2,
) -> None:
    """Reject contours that are unsuitable for a bounded public API query."""

    summary = geometry_summary(geometry)
    if summary.area_m2 > max_area_km2 * 1_000_000:
        raise GeometryLimitError(
            f"Polygon area exceeds the configured {max_area_km2:g} km² limit"
        )


def _coordinates_from_overpass(values: Any) -> list[tuple[float, float]]:
    if not isinstance(values, list):
        return []
    coordinates: list[tuple[float, float]] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        try:
            coordinates.append((float(value["lon"]), float(value["lat"])))
        except (KeyError, TypeError, ValueError):
            continue
    return coordinates


def _is_area(tags: dict[str, str], coordinates: Sequence[tuple[float, float]]) -> bool:
    if len(coordinates) < 4 or coordinates[0] != coordinates[-1]:
        return False
    if tags.get("area") == "no":
        return False
    if tags.get("area") == "yes":
        return True
    if any(key in tags for key in AREA_TAG_KEYS):
        return True
    natural = tags.get("natural")
    return natural is not None and natural not in NON_AREA_NATURAL_VALUES


def _polygonize_lines(lines: list[LineString]) -> BaseGeometry | None:
    if not lines:
        return None
    polygons = list(polygonize(unary_union(lines)))
    return unary_union(polygons) if polygons else None


def overpass_geometry(item: dict[str, Any]) -> BaseGeometry | None:
    """Decode geometry emitted by ``out geom`` for one OSM element."""

    element_type = item.get("type")
    if element_type == "node":
        try:
            return Point(float(item["lon"]), float(item["lat"]))
        except (KeyError, TypeError, ValueError):
            return None

    raw_tags = item.get("tags")
    tags = (
        {str(key): str(value) for key, value in raw_tags.items()}
        if isinstance(raw_tags, dict)
        else {}
    )
    if element_type == "way":
        coordinates = _coordinates_from_overpass(item.get("geometry"))
        if len(coordinates) < 2:
            return None
        geometry: BaseGeometry
        if _is_area(tags, coordinates):
            geometry = Polygon(coordinates)
            if not geometry.is_valid:
                geometry = make_valid(geometry)
            polygons = list(_polygon_parts(geometry))
            if not polygons:
                return LineString(coordinates)
            geometry = unary_union(polygons)
        else:
            geometry = LineString(coordinates)
        return geometry if not geometry.is_empty else None

    if element_type != "relation" or not isinstance(item.get("members"), list):
        return None

    outer_lines: list[LineString] = []
    inner_lines: list[LineString] = []
    all_lines: list[LineString] = []
    for member in item["members"]:
        if not isinstance(member, dict) or member.get("type") != "way":
            continue
        coordinates = _coordinates_from_overpass(member.get("geometry"))
        if len(coordinates) < 2:
            continue
        line = LineString(coordinates)
        all_lines.append(line)
        if member.get("role") == "inner":
            inner_lines.append(line)
        else:
            outer_lines.append(line)

    if tags.get("type") in {"multipolygon", "boundary"}:
        outer = _polygonize_lines(outer_lines)
        if outer is not None:
            inner = _polygonize_lines(inner_lines)
            geometry = outer.difference(inner) if inner is not None else outer
            if not geometry.is_valid:
                geometry = make_valid(geometry)
            polygons = list(_polygon_parts(geometry))
            if polygons:
                return unary_union(polygons)
    if all_lines:
        return unary_union(all_lines)
    return None


class ParcelSpatialAnalyzer:
    """Classify OSM points, lines, and polygons against one parcel."""

    def __init__(self, parcel: BaseGeometry) -> None:
        forward, _ = _metric_transformers(parcel)
        self._parcel = transform(forward.transform, parcel)
        self._project = forward.transform
        self._parcel_area = float(self._parcel.area)

    def analyze(self, geometry: BaseGeometry) -> SpatialRelationData:
        projected = transform(self._project, geometry)
        polygons = list(_polygon_parts(projected))
        if polygons:
            return self._analyze_polygon(unary_union(polygons))
        lines = list(_line_parts(projected))
        if lines:
            return self._analyze_line(unary_union(lines))
        points = list(_point_parts(projected))
        if points:
            return self._analyze_points(points)
        return SpatialRelationData(kind="no_intersection")

    def _analyze_polygon(self, geometry: BaseGeometry) -> SpatialRelationData:
        intersection_area = float(self._parcel.intersection(geometry).area)
        if intersection_area <= AREA_EPSILON_M2:
            return SpatialRelationData(kind="no_intersection")
        if self._parcel.equals(geometry):
            kind = "intersection"
        elif self._parcel.covers(geometry):
            kind = "object_inside_parcel"
        elif geometry.covers(self._parcel):
            kind = "parcel_inside_object"
        else:
            kind = "intersection"
        object_area = float(geometry.area)
        return SpatialRelationData(
            kind=kind,
            intersection_area_m2=round(intersection_area, 3),
            parcel_coverage_percent=round(
                min(100.0, intersection_area / self._parcel_area * 100.0), 6
            )
            if self._parcel_area > 0
            else 0.0,
            object_coverage_percent=round(
                min(100.0, intersection_area / object_area * 100.0), 6
            )
            if object_area > 0
            else 0.0,
        )

    def _analyze_line(self, geometry: BaseGeometry) -> SpatialRelationData:
        if not self._parcel.intersects(geometry) or self._parcel.touches(geometry):
            return SpatialRelationData(kind="no_intersection")
        intersection_length = float(self._parcel.intersection(geometry).length)
        if intersection_length <= LENGTH_EPSILON_M:
            return SpatialRelationData(kind="no_intersection")
        object_length = float(geometry.length)
        kind = (
            "object_inside_parcel"
            if self._parcel.contains(geometry)
            else "intersection"
        )
        return SpatialRelationData(
            kind=kind,
            intersection_length_m=round(intersection_length, 3),
            object_coverage_percent=round(
                min(100.0, intersection_length / object_length * 100.0), 6
            )
            if object_length > 0
            else 0.0,
        )

    def _analyze_points(self, points: list[Point]) -> SpatialRelationData:
        inside_count = sum(self._parcel.contains(point) for point in points)
        if inside_count == 0:
            return SpatialRelationData(kind="no_intersection")
        kind = "object_inside_parcel" if inside_count == len(points) else "intersection"
        return SpatialRelationData(
            kind=kind,
            object_coverage_percent=round(inside_count / len(points) * 100.0, 6),
        )


def geometry_to_geojson(geometry: BaseGeometry) -> dict[str, Any]:
    """Convert a Shapely geometry into a JSON-compatible GeoJSON mapping."""

    return dict(mapping(geometry))
