"""Framework-neutral OpenStreetMap tool implementation."""

from __future__ import annotations

import math
from typing import Any

from typing_extensions import Self

from .client import OsmClient, OsmHttpClient
from .errors import exception_to_tool_error
from .schemas import (
    GeocodeData,
    GeocodingResult,
    NearbyFeature,
    NearbySearchData,
    ReverseGeocodeData,
    ToolResult,
)

OSM_ATTRIBUTION = "© OpenStreetMap contributors"
ODBL_URL = "https://www.openstreetmap.org/copyright"


def _metadata(provider: str) -> dict[str, Any]:
    return {
        "provider": provider,
        "attribution": OSM_ATTRIBUTION,
        "license": "Open Data Commons Open Database License (ODbL)",
        "license_url": ODBL_URL,
    }


def _optional_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _normalize_nominatim_result(item: dict[str, Any]) -> GeocodingResult:
    latitude = _optional_float(item.get("lat"))
    longitude = _optional_float(item.get("lon"))
    display_name = item.get("display_name")
    if latitude is None or longitude is None or not isinstance(display_name, str):
        raise ValueError("Nominatim result has no usable coordinates or name")

    osm_type = item.get("osm_type")
    if osm_type not in {"node", "way", "relation"}:
        osm_type = None
    osm_id = _optional_int(item.get("osm_id"))
    osm_url = (
        f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
        if osm_type is not None and osm_id is not None
        else None
    )

    raw_bbox = item.get("boundingbox")
    bounding_box: tuple[float, float, float, float] | None = None
    if isinstance(raw_bbox, list) and len(raw_bbox) == 4:
        parsed_bbox = tuple(_optional_float(value) for value in raw_bbox)
        if all(value is not None for value in parsed_bbox):
            bounding_box = parsed_bbox  # type: ignore[assignment]

    raw_address = item.get("address")
    address = (
        {str(key): str(value) for key, value in raw_address.items()}
        if isinstance(raw_address, dict)
        else {}
    )
    raw_namedetails = item.get("namedetails")
    namedetails = raw_namedetails if isinstance(raw_namedetails, dict) else {}
    name = item.get("name") or namedetails.get("name")

    return GeocodingResult(
        place_id=_optional_int(item.get("place_id")),
        osm_type=osm_type,
        osm_id=osm_id,
        display_name=display_name,
        name=str(name) if name is not None else None,
        latitude=latitude,
        longitude=longitude,
        bounding_box=bounding_box,
        category=str(item["category"]) if item.get("category") is not None else None,
        type=str(item["type"]) if item.get("type") is not None else None,
        importance=_optional_float(item.get("importance")),
        address=address,
        geojson=item.get("geojson") if isinstance(item.get("geojson"), dict) else None,
        osm_url=osm_url,
    )


def _haversine_distance_m(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    earth_radius_m = 6_371_008.8
    lat_a, lat_b = math.radians(latitude_a), math.radians(latitude_b)
    delta_lat = lat_b - lat_a
    delta_lon = math.radians(longitude_b - longitude_a)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * earth_radius_m * math.asin(math.sqrt(haversine))


def _normalize_overpass_feature(
    item: dict[str, Any],
    *,
    origin_latitude: float,
    origin_longitude: float,
) -> NearbyFeature | None:
    element_type = item.get("type")
    osm_id = _optional_int(item.get("id"))
    if element_type not in {"node", "way", "relation"} or osm_id is None:
        return None

    raw_center = item.get("center")
    center: dict[str, Any] = raw_center if isinstance(raw_center, dict) else {}
    latitude = _optional_float(item.get("lat"))
    longitude = _optional_float(item.get("lon"))
    if latitude is None:
        latitude = _optional_float(center.get("lat"))
    if longitude is None:
        longitude = _optional_float(center.get("lon"))
    if latitude is None or longitude is None:
        return None

    raw_tags = item.get("tags")
    tags = (
        {str(key): str(value) for key, value in raw_tags.items()}
        if isinstance(raw_tags, dict)
        else {}
    )
    name = tags.get("name") or tags.get("brand") or tags.get("operator")
    distance_m = _haversine_distance_m(
        origin_latitude,
        origin_longitude,
        latitude,
        longitude,
    )
    return NearbyFeature(
        element_type=element_type,
        osm_id=osm_id,
        name=name,
        latitude=latitude,
        longitude=longitude,
        distance_m=round(distance_m, 1),
        tags=tags,
        osm_url=f"https://www.openstreetmap.org/{element_type}/{osm_id}",
    )


class OsmTools:
    """High-level operations exposed to agents and MCP clients."""

    def __init__(self, client: OsmClient | None = None) -> None:
        self._client = client or OsmHttpClient()
        self._owns_client = client is None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_client:
            await self._client.close()

    async def geocode(
        self,
        query: str,
        limit: int = 5,
        country_codes: list[str] | None = None,
        language: str = "ru",
        include_geometry: bool = False,
    ) -> ToolResult[GeocodeData]:
        try:
            raw_results = await self._client.geocode(
                query,
                limit=limit,
                country_codes=country_codes or [],
                language=language,
                include_geometry=include_geometry,
            )
            results = [_normalize_nominatim_result(item) for item in raw_results]
            return ToolResult[GeocodeData].success(
                GeocodeData(query=query, results=results),
                metadata=_metadata("Nominatim"),
            )
        except Exception as exc:  # noqa: BLE001 - stable tool boundary
            return ToolResult[GeocodeData].failure(
                exception_to_tool_error(exc),
                metadata=_metadata("Nominatim"),
            )

    async def reverse_geocode(
        self,
        latitude: float,
        longitude: float,
        zoom: int = 18,
        language: str = "ru",
        include_geometry: bool = False,
    ) -> ToolResult[ReverseGeocodeData]:
        try:
            raw_result = await self._client.reverse_geocode(
                latitude,
                longitude,
                zoom=zoom,
                language=language,
                include_geometry=include_geometry,
            )
            if raw_result is None:
                return ToolResult[ReverseGeocodeData].failure(
                    error=exception_to_tool_error(
                        LookupError(
                            "No OpenStreetMap object found at these coordinates"
                        )
                    ),
                    metadata=_metadata("Nominatim"),
                )
            result = _normalize_nominatim_result(raw_result)
            return ToolResult[ReverseGeocodeData].success(
                ReverseGeocodeData(
                    requested_latitude=latitude,
                    requested_longitude=longitude,
                    result=result,
                ),
                metadata=_metadata("Nominatim"),
            )
        except Exception as exc:  # noqa: BLE001 - stable tool boundary
            return ToolResult[ReverseGeocodeData].failure(
                exception_to_tool_error(exc),
                metadata=_metadata("Nominatim"),
            )

    async def search_nearby(
        self,
        latitude: float,
        longitude: float,
        tags: dict[str, str | None],
        radius_m: int = 500,
        limit: int = 20,
    ) -> ToolResult[NearbySearchData]:
        try:
            raw_features = await self._client.search_nearby(
                latitude,
                longitude,
                radius_m=radius_m,
                tags=tags,
                limit=limit,
            )
            features = [
                feature
                for item in raw_features
                if (
                    feature := _normalize_overpass_feature(
                        item,
                        origin_latitude=latitude,
                        origin_longitude=longitude,
                    )
                )
                is not None
            ]
            features.sort(key=lambda feature: feature.distance_m)
            features = features[:limit]
            return ToolResult[NearbySearchData].success(
                NearbySearchData(
                    latitude=latitude,
                    longitude=longitude,
                    radius_m=radius_m,
                    tags=tags,
                    returned_count=len(features),
                    limit_reached=len(raw_features) >= limit,
                    features=features,
                ),
                metadata=_metadata("Overpass API"),
            )
        except Exception as exc:  # noqa: BLE001 - stable tool boundary
            return ToolResult[NearbySearchData].failure(
                exception_to_tool_error(exc),
                metadata=_metadata("Overpass API"),
            )
