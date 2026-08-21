from pyosm_agents.core import OsmTools, create_default_registry

from .fakes import FakeOsmClient


def test_registry_contains_only_public_first_release_tools() -> None:
    registry = create_default_registry(OsmTools(FakeOsmClient()))

    assert registry.names() == [
        "osm_geocode",
        "osm_reverse_geocode",
        "osm_search_nearby",
    ]


async def test_registry_validates_arguments() -> None:
    registry = create_default_registry(OsmTools(FakeOsmClient()))

    result = await registry.call(
        "osm_search_nearby",
        {"latitude": 56, "longitude": 44, "radius_m": 100_000, "tags": {}},
    )

    assert not result.ok
    assert result.error is not None
    assert result.error.code == "invalid_arguments"


async def test_registry_invokes_tool() -> None:
    client = FakeOsmClient()
    registry = create_default_registry(OsmTools(client))

    result = await registry.call(
        "osm_geocode",
        {"query": "Нижний Новгород", "country_codes": ["RU"]},
    )

    assert result.ok
    assert client.calls[0][1]["country_codes"] == ["ru"]


async def test_unknown_tool_has_stable_error() -> None:
    registry = create_default_registry(OsmTools(FakeOsmClient()))

    result = await registry.call("missing", {})

    assert not result.ok
    assert result.error is not None
    assert result.error.code == "unknown_tool"
