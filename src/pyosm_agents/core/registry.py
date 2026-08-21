"""Neutral tool registry shared by all framework adapters."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError
from typing_extensions import Self

from .errors import exception_to_tool_error
from .schemas import (
    AnalyzeLandParcelInput,
    GeocodeInput,
    NearbySearchInput,
    PolygonSearchInput,
    ReverseGeocodeInput,
    ToolError,
    ToolResult,
)
from .tools import OsmTools

ToolHandler = Callable[..., Awaitable[ToolResult[Any]]]
CloseCallback = Callable[[], Awaitable[None]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: ToolHandler

    def json_schema(self) -> dict[str, Any]:
        return self.input_model.model_json_schema()


class ToolRegistry:
    """Discover, describe, and invoke OSM tools without an agent framework."""

    def __init__(
        self,
        definitions: list[ToolDefinition],
        *,
        close_callback: CloseCallback | None = None,
    ) -> None:
        self._definitions = {definition.name: definition for definition in definitions}
        if len(self._definitions) != len(definitions):
            raise ValueError("Tool names must be unique")
        self._close_callback = close_callback

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._close_callback is not None:
            await self._close_callback()

    def names(self) -> list[str]:
        return list(self._definitions)

    def get(self, name: str) -> ToolDefinition:
        return self._definitions[name]

    def json_schema(self, name: str) -> dict[str, Any]:
        return self.get(name).json_schema()

    def json_schemas(self) -> dict[str, dict[str, Any]]:
        return {
            name: definition.json_schema()
            for name, definition in self._definitions.items()
        }

    async def call(self, name: str, arguments: dict[str, Any]) -> ToolResult[Any]:
        definition = self._definitions.get(name)
        if definition is None:
            return ToolResult[Any].failure(
                ToolError(code="unknown_tool", message=f"Unknown tool: {name}")
            )
        try:
            validated = definition.input_model.model_validate(arguments)
        except ValidationError as exc:
            return ToolResult[Any].failure(exception_to_tool_error(exc))
        return await definition.handler(**validated.model_dump())


def create_default_registry(tools: OsmTools | None = None) -> ToolRegistry:
    """Create the framework-neutral OpenStreetMap registry."""

    service = tools or OsmTools()
    return ToolRegistry(
        [
            ToolDefinition(
                name="osm_geocode",
                description=(
                    "Find OpenStreetMap places by a human-readable address or name "
                    "using Nominatim."
                ),
                input_model=GeocodeInput,
                handler=service.geocode,
            ),
            ToolDefinition(
                name="osm_reverse_geocode",
                description=(
                    "Find the nearest suitable OpenStreetMap object or address for "
                    "WGS84 coordinates using Nominatim."
                ),
                input_model=ReverseGeocodeInput,
                handler=service.reverse_geocode,
            ),
            ToolDefinition(
                name="osm_search_nearby",
                description=(
                    "Find nearby OpenStreetMap nodes, ways, and relations by one to "
                    "five exact tags using a bounded generated Overpass query."
                ),
                input_model=NearbySearchInput,
                handler=service.search_nearby,
            ),
            ToolDefinition(
                name="osm_search_in_polygon",
                description=(
                    "Find OSM objects by exact tags inside or intersecting a WGS84 "
                    "GeoJSON polygon, then verify spatial relations locally."
                ),
                input_model=PolygonSearchInput,
                handler=service.search_in_polygon,
            ),
            ToolDefinition(
                name="osm_analyze_land_parcel",
                description=(
                    "Resolve a land parcel by cadastral number through NSPD, then "
                    "analyze buildings, transport, land use, infrastructure, and "
                    "POI blocks from OpenStreetMap against its exact contour."
                ),
                input_model=AnalyzeLandParcelInput,
                handler=service.analyze_land_parcel,
            ),
        ],
        close_callback=service.close,
    )
