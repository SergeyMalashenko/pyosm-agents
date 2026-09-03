from pyosm_agents.core import OsmTools

from .fakes import PARCEL_GEOMETRY, FakeOsmClient


async def test_geocode_normalizes_result_and_attribution() -> None:
    client = FakeOsmClient()
    tools = OsmTools(client)

    result = await tools.geocode(
        "Нижний Новгород",
        country_codes=["ru"],
        include_geometry=True,
    )

    assert result.ok
    assert result.data is not None
    assert result.data.results[0].osm_url is not None
    assert result.data.results[0].osm_url.endswith("/relation/200")
    assert result.data.results[0].bounding_box == (56.1, 56.5, 43.6, 44.3)
    assert result.data.results[0].geojson is not None
    assert result.metadata["attribution"] == "© OpenStreetMap contributors"


async def test_reverse_geocode_returns_requested_coordinates() -> None:
    tools = OsmTools(FakeOsmClient())

    result = await tools.reverse_geocode(56.3287, 44.002)

    assert result.ok
    assert result.data is not None
    assert result.data.requested_latitude == 56.3287
    assert result.data.result.name == "Нижний Новгород"


async def test_reverse_geocode_reports_not_found() -> None:
    client = FakeOsmClient()
    client.reverse_response = None
    tools = OsmTools(client)

    result = await tools.reverse_geocode(0, 0)

    assert not result.ok
    assert result.error is not None
    assert result.error.code == "not_found"


async def test_nearby_search_normalizes_nodes_and_way_centers() -> None:
    tools = OsmTools(FakeOsmClient())

    result = await tools.search_nearby(
        56.3287,
        44.002,
        tags={"amenity": "hospital"},
        radius_m=1000,
        limit=20,
    )

    assert result.ok
    assert result.data is not None
    assert result.data.returned_count == 2
    assert result.data.features[0].element_type == "node"
    assert result.data.features[1].element_type == "way"
    assert result.data.features[1].osm_url.endswith("/way/301")
    assert result.metadata["provider"] == "Overpass API"


async def test_caller_owned_client_is_not_closed() -> None:
    client = FakeOsmClient()
    tools = OsmTools(client)

    await tools.close()

    assert not client.closed


async def test_polygon_search_classifies_exact_geometry() -> None:
    client = FakeOsmClient()
    tools = OsmTools(client)

    result = await tools.search_in_polygon(
        PARCEL_GEOMETRY,
        tags={"building": None},
        include_geometry=True,
    )

    assert result.ok
    assert result.data is not None
    assert result.data.returned_count == 3
    building = next(
        feature for feature in result.data.features if feature.osm_id == 401
    )
    assert building.relation.kind == "object_inside_parcel"
    assert building.relation.intersection_area_m2 > 0
    assert building.geojson is not None
    road = next(feature for feature in result.data.features if feature.osm_id == 402)
    assert road.relation.kind == "intersection"
    assert road.relation.intersection_length_m > 0


async def test_area_analysis_expands_circle_and_groups_nearby_features() -> None:
    client = FakeOsmClient()
    tools = OsmTools(client)

    result = await tools.analyze_area(
        PARCEL_GEOMETRY,
        margin_m=1000,
        blocks=["forests", "lakes", "rivers", "streams", "roads"],
        limit_per_block=10,
        include_geometry=False,
    )

    assert result.ok
    assert result.data is not None
    counts = {block.block: block.returned_count for block in result.data.blocks}
    assert counts == {
        "forests": 1,
        "lakes": 2,
        "rivers": 1,
        "streams": 1,
        "roads": 2,
    }
    assert result.data.search_area.margin_m == 1000
    assert result.data.search_area.search_radius_m == (
        result.data.search_area.parcel_minimum_radius_m + 1000
    )
    assert result.data.search_area.geojson["type"] == "Polygon"
    forest = next(
        feature
        for block in result.data.blocks
        for feature in block.features
        if feature.osm_id == 406
    )
    assert forest.geometry_type == "Polygon"
    assert forest.geojson is not None
    assert forest.relation.kind == "no_intersection"
    assert forest.search_relation == "inside_search_area"
    assert forest.distance_to_parcel_m is not None
    stream = next(
        feature
        for block in result.data.blocks
        for feature in block.features
        if feature.osm_id == 409
    )
    assert stream.geometry_type == "LineString"
    assert stream.geojson is None
    assert forest.distance_to_parcel_m > 0
    untyped_waterbody = next(
        feature
        for block in result.data.blocks
        for feature in block.features
        if feature.osm_id == 410
    )
    assert untyped_waterbody.name == "Дракинский карьер"
    assert untyped_waterbody.geometry_type == "Polygon"
    assert untyped_waterbody.geojson is not None
    crossing = next(
        feature
        for block in result.data.blocks
        for feature in block.features
        if feature.osm_id == 405
    )
    assert crossing.search_relation in {
        "inside_search_area",
        "intersects_search_area",
    }
    returned_ids = {
        feature.osm_id
        for block in result.data.blocks
        for feature in block.features
    }
    assert 404 not in returned_ids
    assert client.calls[-1][0] == "search_bbox"
    west, south, east, north = client.calls[-1][1]["bounds"]
    assert west < 44.0018 and south < 56.3286
    assert east > 44.0024 and north > 56.3291
