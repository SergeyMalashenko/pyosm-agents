from __future__ import annotations

import httpx

from pyosm_agents.core.client import (
    OsmHttpClient,
    build_overpass_bbox_query,
    build_overpass_query,
)


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


def test_polygon_query_uses_bbox_candidates_and_or_filters() -> None:
    query = build_overpass_bbox_query(
        (44.0, 56.0, 44.1, 56.1),
        tag_filters=[{"building": None}, {"amenity": "school"}],
        limit=100,
    )

    assert "nwr(56.0000000,44.0000000,56.1000000,44.1000000)" in query
    assert '["building"]' in query
    assert '["amenity"="school"]' in query
    assert "out geom qt 100;" in query


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
    client = OsmHttpClient(
        http_client=http,
        user_agent="test-agent/1.0",
        overpass_retry_delay_s=0,
    )

    result = await client.search_nearby(
        56,
        44,
        radius_m=500,
        tags={"amenity": "hospital"},
        limit=10,
    )

    assert result == []
    await http.aclose()


async def test_polygon_search_posts_geometry_query() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        assert "nwr%2856" in body
        assert "geom" in body
        return httpx.Response(200, request=request, json={"elements": []})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OsmHttpClient(
        http_client=http,
        user_agent="test-agent/1.0",
        overpass_retry_delay_s=0,
    )

    result = await client.search_bbox(
        (44.0, 56.0, 44.1, 56.1),
        tag_filters=[{"building": None}],
        limit=10,
    )

    assert result == []
    await http.aclose()


async def test_overpass_retries_one_transient_failure() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if request_count == 1:
            return httpx.Response(504, request=request)
        return httpx.Response(200, request=request, json={"elements": []})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OsmHttpClient(
        http_client=http,
        user_agent="test-agent/1.0",
        overpass_retry_delay_s=0,
    )

    result = await client.search_bbox(
        (44.0, 56.0, 44.1, 56.1),
        tag_filters=[{"building": None}],
        limit=10,
    )

    assert result == []
    assert request_count == 2
    await http.aclose()
