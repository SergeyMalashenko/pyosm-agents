from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from pyosm_agents.core import OsmTools
from pyosm_agents.mcp import _build_parser, create_mcp_server

from .fakes import FakeOsmClient


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


def test_mcp_server_registers_three_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pyosm_agents.mcp._load_mcp_server_class", lambda: FakeFastMCP)

    server = create_mcp_server(OsmTools(FakeOsmClient()))

    assert list(server.tools) == [
        "osm_geocode",
        "osm_reverse_geocode",
        "osm_search_nearby",
    ]
    assert server.kwargs["stateless_http"] is True
    assert server.kwargs["json_response"] is True
    assert server.kwargs["port"] == 8002


async def test_mcp_tool_uses_structured_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("pyosm_agents.mcp._load_mcp_server_class", lambda: FakeFastMCP)
    server = create_mcp_server(OsmTools(FakeOsmClient()))

    result = await server.tools["osm_geocode"]("Нижний Новгород")

    assert result.ok
    assert result.data is not None
    assert result.data.results[0].osm_id == 200


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
