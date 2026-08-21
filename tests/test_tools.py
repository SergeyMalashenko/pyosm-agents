from shapely.geometry import mapping

from pyosm_agents.core import OsmTools

from .fakes import FakeOsmClient, FakeParcelProvider


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
    parcel_provider = FakeParcelProvider()
    tools = OsmTools(client, parcel_provider=parcel_provider)

    result = await tools.search_in_polygon(
        dict(mapping(parcel_provider.record.geometry)),
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


async def test_land_parcel_analysis_groups_features_into_blocks() -> None:
    client = FakeOsmClient()
    parcel_provider = FakeParcelProvider()
    tools = OsmTools(client, parcel_provider=parcel_provider)

    result = await tools.analyze_land_parcel(
        "52:24:0000000:2216",
        blocks=["buildings", "transport", "poi"],
        limit_per_block=10,
    )

    assert result.ok
    assert result.data is not None
    assert parcel_provider.queries == ["52:24:0000000:2216"]
    counts = {block.block: block.returned_count for block in result.data.blocks}
    assert counts == {"buildings": 1, "transport": 1, "poi": 1}
    assert result.data.parcel.address == "Нижегородская область, тестовый участок"
    assert client.calls[-1][0] == "search_bbox"


async def test_caller_owned_parcel_provider_is_not_closed() -> None:
    provider = FakeParcelProvider()
    tools = OsmTools(FakeOsmClient(), parcel_provider=provider)

    await tools.close()

    assert not provider.closed
