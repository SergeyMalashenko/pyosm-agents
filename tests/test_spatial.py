from shapely.geometry import LineString, Point, Polygon, mapping

from pyosm_agents.core.spatial import (
    ParcelSpatialAnalyzer,
    SearchAreaAnalyzer,
    overpass_geometry,
    prepare_polygon_geometry,
    validate_query_contour,
)


def test_prepare_polygon_repairs_and_validates_query_contour() -> None:
    polygon = Polygon([(44.0, 56.0), (44.01, 56.0), (44.01, 56.01), (44.0, 56.0)])

    prepared = prepare_polygon_geometry(dict(mapping(polygon)))
    validate_query_contour(prepared)

    assert prepared.is_valid


def test_spatial_analyzer_ignores_boundary_only_contact() -> None:
    parcel = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    analyzer = ParcelSpatialAnalyzer(parcel)

    point_result = analyzer.analyze(Point(0, 0.5))
    line_result = analyzer.analyze(LineString([(0, 0), (0, 1)]))

    assert point_result.kind == "no_intersection"
    assert line_result.kind == "no_intersection"


def test_spatial_analyzer_classifies_four_relations() -> None:
    parcel = Polygon([(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)])
    analyzer = ParcelSpatialAnalyzer(parcel)

    assert analyzer.analyze(Point(3, 3)).kind == "no_intersection"
    assert analyzer.analyze(Point(1, 1)).kind == "object_inside_parcel"
    assert (
        analyzer.analyze(Polygon([(1, 1), (3, 1), (3, 3), (1, 3), (1, 1)])).kind
        == "intersection"
    )
    assert (
        analyzer.analyze(
            Polygon([(-1, -1), (3, -1), (3, 3), (-1, 3), (-1, -1)])
        ).kind
        == "parcel_inside_object"
    )


def test_search_area_uses_minimum_radius_plus_metric_margin() -> None:
    parcel = Polygon(
        [
            (44.0018, 56.3286),
            (44.0024, 56.3286),
            (44.0024, 56.3291),
            (44.0018, 56.3291),
            (44.0018, 56.3286),
        ]
    )
    analyzer = SearchAreaAnalyzer(parcel, margin_m=1000)

    assert analyzer.area.parcel_minimum_radius_m > 0
    assert analyzer.area.search_radius_m == (
        analyzer.area.parcel_minimum_radius_m + 1000
    )
    assert analyzer.area.geometry.covers(parcel)
    assert analyzer.intersects_search_area(Point(44.0100, 56.3288))
    assert not analyzer.intersects_search_area(Point(44.0400, 56.3288))
    assert analyzer.distance_to_parcel_m(Point(44.0100, 56.3288)) > 0


def test_search_area_includes_a_line_crossing_its_boundary() -> None:
    parcel = Polygon(
        [
            (44.0018, 56.3286),
            (44.0024, 56.3286),
            (44.0024, 56.3291),
            (44.0018, 56.3291),
            (44.0018, 56.3286),
        ]
    )
    analyzer = SearchAreaAnalyzer(parcel, margin_m=1000)
    crossing = LineString([(43.9800, 56.3350), (44.0300, 56.3350)])

    assert analyzer.intersects_search_area(crossing)
    assert analyzer.search_relation(crossing) == "intersects_search_area"


def test_overpass_way_is_decoded_as_polygon_or_line() -> None:
    building = overpass_geometry(
        {
            "type": "way",
            "tags": {"building": "yes"},
            "geometry": [
                {"lon": 0, "lat": 0},
                {"lon": 1, "lat": 0},
                {"lon": 1, "lat": 1},
                {"lon": 0, "lat": 0},
            ],
        }
    )
    road = overpass_geometry(
        {
            "type": "way",
            "tags": {"highway": "service"},
            "geometry": [{"lon": 0, "lat": 0}, {"lon": 1, "lat": 1}],
        }
    )

    assert building is not None and building.geom_type == "Polygon"
    assert road is not None and road.geom_type == "LineString"
