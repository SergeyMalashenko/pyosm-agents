from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from pyosm_agents.core import OsmTools
from pyosm_agents.mcp import _build_parser, _run_server, create_mcp_server

from .fakes import FakeOsmClient, PARCEL_GEOMETRY


class FakeFastMCP:
    def __init__(self, name: str, **kwargs: Any) -> None:
        self.name = name
        self.kwargs = kwargs
        self.tools: dict[str, Callable[..., Any]] = {}

    def tool(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
            self.tools[function.__name__] = function
            return function

        return decorator


def test_mcp_server_registers_five_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pyosm_agents.mcp._load_mcp_server_class", lambda: FakeFastMCP)

    server = create_mcp_server(OsmTools(FakeOsmClient()))

    assert list(server.tools) == [
        "osm_geocode",
        "osm_reverse_geocode",
        "osm_search_nearby",
        "osm_search_in_polygon",
        "osm_analyze_area",
    ]
    assert server.kwargs["stateless_http"] is True
    assert server.kwargs["json_response"] is True
    assert server.kwargs["port"] == 8002
    assert "lifespan" not in server.kwargs


async def test_mcp_tool_uses_structured_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("pyosm_agents.mcp._load_mcp_server_class", lambda: FakeFastMCP)
    server = create_mcp_server(OsmTools(FakeOsmClient()))

    result = await server.tools["osm_geocode"]("Нижний Новгород")

    assert result.ok
    assert result.data is not None
    assert result.data.results[0].osm_id == 200


async def test_mcp_area_tool_accepts_caller_provided_contour(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("pyosm_agents.mcp._load_mcp_server_class", lambda: FakeFastMCP)
    server = create_mcp_server(OsmTools(FakeOsmClient()))

    result = await server.tools["osm_analyze_area"](
        PARCEL_GEOMETRY,
        blocks=["forests", "lakes", "rivers", "streams", "roads"],
    )

    assert result.ok
    assert result.data is not None
    assert result.data.search_area.margin_m == 1000


async def test_tools_remain_available_across_stateless_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("pyosm_agents.mcp._load_mcp_server_class", lambda: FakeFastMCP)
    service = OsmTools(FakeOsmClient())
    service.close = AsyncMock(wraps=service.close)  # type: ignore[method-assign]
    server = create_mcp_server(service)

    first = await server.tools["osm_geocode"]("Нижний Новгород")
    second = await server.tools["osm_geocode"]("Москва")

    assert first.ok
    assert second.ok
    service.close.assert_not_awaited()


@pytest.mark.filterwarnings("ignore:Field 'lifespan' has an incomplete definition")
async def test_real_stateless_http_call_survives_initialize_request() -> None:
    pytest.importorskip("mcp.server.fastmcp")

    client = FakeOsmClient()
    service = OsmTools(client)
    # Reproduce ownership of the default production service: the previous MCP
    # lifespan closed its shared client after the initialize HTTP request.
    service._owns_client = True
    app = create_mcp_server(service).streamable_http_app()
    headers = {
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
    }

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://127.0.0.1:8002",
        ) as http,
    ):
        initialized = await http.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1"},
                },
            },
        )
        called = await http.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "osm_analyze_area",
                    "arguments": {
                        "geometry": PARCEL_GEOMETRY,
                        "source_crs": "EPSG:4326",
                        "margin_m": 1000,
                        "blocks": ["forests", "lakes", "rivers", "roads"],
                        "limit_per_block": 5,
                        "include_geometry": False,
                    },
                },
            },
        )

    assert initialized.status_code == 200
    assert called.status_code == 200
    assert called.json()["result"]["structuredContent"]["ok"] is True
    assert not client.closed


@pytest.mark.parametrize("transport", ["stdio", "streamable-http"])
async def test_cli_runner_closes_service_at_process_shutdown(
    transport: str,
) -> None:
    class FakeRunnableServer:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def run_stdio_async(self) -> None:
            self.calls.append("stdio")

        async def run_streamable_http_async(self) -> None:
            self.calls.append("streamable-http")

    server = FakeRunnableServer()
    service = OsmTools(FakeOsmClient())
    service.close = AsyncMock(wraps=service.close)  # type: ignore[method-assign]

    await _run_server(server, service, transport)

    assert server.calls == [transport]
    service.close.assert_awaited_once_with()


def test_cli_defaults_to_stdio_and_port_8002() -> None:
    args = _build_parser().parse_args([])

    assert args.transport == "stdio"
    assert args.host == "127.0.0.1"
    assert args.port == 8002


@pytest.mark.parametrize("port", [0, 65536])
def test_mcp_server_rejects_invalid_port(
    monkeypatch: pytest.MonkeyPatch,
    port: int,
) -> None:
    monkeypatch.setattr("pyosm_agents.mcp._load_mcp_server_class", lambda: FakeFastMCP)

    with pytest.raises(ValueError, match="port"):
        create_mcp_server(OsmTools(FakeOsmClient()), port=port)
