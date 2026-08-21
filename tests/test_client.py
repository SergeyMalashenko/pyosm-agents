from __future__ import annotations

import httpx

from pyosm_agents.core.client import OsmHttpClient, build_overpass_query


def test_overpass_query_is_bounded_and_escaped() -> None:
    query = build_overpass_query(
        56.3287,
        44.002,
        radius_m=1000,
        tags={"amenity": "hospital", "name": None},
        limit=20,
    )

    assert "[out:json][timeout:25]" in query
    assert 'node(around:1000,56.3287000,44.0020000)["amenity"="hospital"]' in query
    assert '["name"]' in query
    assert "out tags center qt 20;" in query


async def test_nominatim_response_is_cached() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        assert request.headers["user-agent"] == "test-agent/1.0"
        return httpx.Response(
            200,
            request=request,
            json=[{"display_name": "Test", "lat": "1", "lon": "2"}],
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OsmHttpClient(
        http_client=http,
        user_agent="test-agent/1.0",
        nominatim_min_interval_s=0,
    )
    first = await client.geocode(
        "Test",
        limit=1,
        country_codes=[],
        language="en",
        include_geometry=False,
    )
    second = await client.geocode(
        "Test",
        limit=1,
        country_codes=[],
        language="en",
        include_geometry=False,
    )

    assert first == second
    assert request_count == 1
    await http.aclose()


async def test_overpass_posts_generated_query() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert "data=" in request.content.decode()
        return httpx.Response(200, request=request, json={"elements": []})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OsmHttpClient(http_client=http, user_agent="test-agent/1.0")

    result = await client.search_nearby(
        56,
        44,
        radius_m=500,
        tags={"amenity": "hospital"},
        limit=10,
    )

    assert result == []
    await http.aclose()
