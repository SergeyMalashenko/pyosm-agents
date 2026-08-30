"""Model Context Protocol server for OpenStreetMap tools."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Any, Literal

from .core import (
    AreaOsmAnalysisData,
    GeocodeData,
    NearbySearchData,
    OsmBlockName,
    OsmTools,
    PolygonSearchData,
    ReverseGeocodeData,
    ToolResult,
    create_default_registry,
)

DEFAULT_INSTRUCTIONS = (
    "Use osm_analyze_area for natural and road analysis around a caller-provided "
    "WGS84 GeoJSON contour. It constructs the minimum enclosing circle, adds "
    "the requested metric margin, and filters Overpass candidates locally. "
    "Use osm_search_in_polygon for exact-tag searches in GeoJSON polygons, "
    "osm_geocode for names or addresses, "
    "osm_reverse_geocode for coordinates, and osm_search_nearby for radial "
    "searches. Arbitrary Overpass QL is not supported. Boundary-only contacts "
    "are excluded from polygon results. Treat OSM data as community-maintained "
    "and potentially incomplete. Preserve the OpenStreetMap attribution."
)


class MCPDependencyError(RuntimeError):
    """Raised when the optional MCP SDK dependency is unavailable."""


def _load_mcp_server_class() -> type[Any]:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise MCPDependencyError(
            "MCP support is not installed. Install it with "
            "`pip install 'pyosm-agents[mcp]'`."
        ) from exc
    return FastMCP


def create_mcp_server(
    tools: OsmTools | None = None,
    *,
    name: str = "pyosm",
    instructions: str = DEFAULT_INSTRUCTIONS,
    host: str = "127.0.0.1",
    port: int = 8002,
    streamable_http_path: str = "/mcp",
    stateless_http: bool = True,
    json_response: bool = True,
) -> Any:
    """Create a FastMCP server exposing OpenStreetMap tools."""

    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    if not streamable_http_path.startswith("/"):
        raise ValueError("streamable_http_path must start with '/'")

    service = tools or OsmTools()
    registry = create_default_registry(service)

    server_class = _load_mcp_server_class()
    server = server_class(
        name,
        instructions=instructions,
        host=host,
        port=port,
        streamable_http_path=streamable_http_path,
        stateless_http=stateless_http,
        json_response=json_response,
    )

    @server.tool()
    async def osm_geocode(
        query: str,
        limit: int = 5,
        country_codes: list[str] | None = None,
        language: str = "ru",
        include_geometry: bool = False,
    ) -> ToolResult[GeocodeData]:
        """Find OpenStreetMap places by address or name.

        Args:
            query: Human-readable address, place name, or both.
            limit: Maximum number of results, from 1 to 10.
            country_codes: Optional two-letter ISO 3166-1 country-code filter,
                for example ``["ru"]``.
            language: Preferred result language, for example ``ru`` or ``en``.
            include_geometry: Include the matched object's GeoJSON geometry.
        """

        arguments: dict[str, Any] = {
            "query": query,
            "limit": limit,
            "language": language,
            "include_geometry": include_geometry,
        }
        if country_codes is not None:
            arguments["country_codes"] = country_codes
        result = await registry.call("osm_geocode", arguments)
        return ToolResult[GeocodeData].model_validate(result.model_dump())

    @server.tool()
    async def osm_reverse_geocode(
        latitude: float,
        longitude: float,
        zoom: int = 18,
        language: str = "ru",
        include_geometry: bool = False,
    ) -> ToolResult[ReverseGeocodeData]:
        """Describe the nearest suitable OSM object at WGS84 coordinates.

        Args:
            latitude: Latitude between -90 and 90.
            longitude: Longitude between -180 and 180.
            zoom: Address-detail level from 0 (country) to 18 (building).
            language: Preferred result language, for example ``ru`` or ``en``.
            include_geometry: Include the matched object's GeoJSON geometry.
        """

        result = await registry.call(
            "osm_reverse_geocode",
            {
                "latitude": latitude,
                "longitude": longitude,
                "zoom": zoom,
                "language": language,
                "include_geometry": include_geometry,
            },
        )
        return ToolResult[ReverseGeocodeData].model_validate(result.model_dump())

    @server.tool()
    async def osm_search_nearby(
        latitude: float,
        longitude: float,
        tags: dict[str, str | None],
        radius_m: int = 500,
        limit: int = 20,
    ) -> ToolResult[NearbySearchData]:
        """Find nearby OSM objects by exact tags using a bounded search.

        Args:
            latitude: Search-center latitude between -90 and 90.
            longitude: Search-center longitude between -180 and 180.
            tags: One to five OSM tags combined with AND. Use a string for an
                exact value, for example ``{"amenity": "hospital"}``, or null
                to match any value, for example ``{"name": null}``.
            radius_m: Search radius from 1 to 5000 metres.
            limit: Maximum number of results, from 1 to 100.
        """

        result = await registry.call(
            "osm_search_nearby",
            {
                "latitude": latitude,
                "longitude": longitude,
                "tags": tags,
                "radius_m": radius_m,
                "limit": limit,
            },
        )
        return ToolResult[NearbySearchData].model_validate(result.model_dump())

    @server.tool()
    async def osm_search_in_polygon(
        geometry: dict[str, Any],
        tags: dict[str, str | None],
        limit: int = 100,
        include_geometry: bool = False,
    ) -> ToolResult[PolygonSearchData]:
        """Find and geometrically verify OSM objects in a WGS84 contour.

        Args:
            geometry: GeoJSON Polygon or MultiPolygon in WGS84 longitude/latitude
                order. Interior rings participate in local verification.
            tags: One to five exact OSM tags combined with AND. Use null to match
                any value for a key, for example ``{"building": null}``.
            limit: Maximum number of Overpass candidates, from 1 to 500.
            include_geometry: Include each matched OSM object's GeoJSON geometry.
        """

        result = await registry.call(
            "osm_search_in_polygon",
            {
                "geometry": geometry,
                "tags": tags,
                "limit": limit,
                "include_geometry": include_geometry,
            },
        )
        return ToolResult[PolygonSearchData].model_validate(result.model_dump())

    @server.tool()
    async def osm_analyze_area(
        geometry: dict[str, Any],
        source_crs: Literal["EPSG:4326"] = "EPSG:4326",
        margin_m: int = 1000,
        blocks: list[OsmBlockName] | None = None,
        limit_per_block: int = 50,
        include_geometry: bool = False,
    ) -> ToolResult[AreaOsmAnalysisData]:
        """Analyze forests, waters, streams, and roads around a WGS84 contour.

        Args:
            geometry: WGS84 GeoJSON Polygon or MultiPolygon.
            source_crs: Coordinate reference system; currently only
                ``EPSG:4326`` is accepted.
            margin_m: Metres added to the contour's minimum enclosing radius.
            blocks: Any of ``forests``, ``lakes``, ``rivers``, ``streams``,
                and ``roads``. Defaults to all five blocks. Forest, lake, and
                river contours are always included in the response.
            limit_per_block: Maximum returned objects per block, from 1 to 100.
            include_geometry: Include matched OSM GeoJSON geometries. Keep false
                for compact LLM responses.
        """

        arguments: dict[str, Any] = {
            "geometry": geometry,
            "source_crs": source_crs,
            "margin_m": margin_m,
            "limit_per_block": limit_per_block,
            "include_geometry": include_geometry,
        }
        if blocks is not None:
            arguments["blocks"] = blocks
        result = await registry.call("osm_analyze_area", arguments)
        return ToolResult[AreaOsmAnalysisData].model_validate(result.model_dump())

    return server


async def _run_server(
    server: Any,
    service: OsmTools,
    transport: str,
) -> None:
    """Run FastMCP and close shared clients once the whole process stops.

    FastMCP's low-level lifespan is scoped to an MCP session. In stateless HTTP
    mode that means one lifespan per HTTP request, so it must not own clients
    shared by all requests.
    """

    try:
        if transport == "stdio":
            await server.run_stdio_async()
        elif transport == "streamable-http":
            await server.run_streamable_http_async()
        else:  # pragma: no cover - argparse restricts public CLI values
            raise ValueError(f"Unsupported MCP transport: {transport}")
    finally:
        await service.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyosm-mcp",
        description="Run OpenStreetMap tools as a Model Context Protocol server.",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8002)
    parser.add_argument("--path", default="/mcp", dest="streamable_http_path")
    parser.add_argument(
        "--stateful-http",
        action="store_true",
        help="Keep MCP HTTP sessions instead of stateless request handling",
    )
    parser.add_argument(
        "--sse-response",
        action="store_true",
        help="Stream HTTP responses as SSE instead of a single JSON body",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Run the MCP server from the ``pyosm-mcp`` console command."""

    args = _build_parser().parse_args(argv)
    try:
        import anyio

        service = OsmTools()
        server = create_mcp_server(
            service,
            host=args.host,
            port=args.port,
            streamable_http_path=args.streamable_http_path,
            stateless_http=not args.stateful_http,
            json_response=not args.sse_response,
        )
    except (ImportError, MCPDependencyError) as exc:
        raise SystemExit(
            "MCP support is not installed. Install it with "
            "`pip install 'pyosm-agents[mcp]'`."
        ) from exc
    anyio.run(_run_server, server, service, args.transport)


if __name__ == "__main__":  # pragma: no cover
    main()
