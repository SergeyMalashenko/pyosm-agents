"""Agent-safe tools for OpenStreetMap services."""

from .core import (
    AreaOsmAnalysisData,
    GeocodeData,
    NearbySearchData,
    OsmBlockName,
    OsmTools,
    PolygonSearchData,
    ReverseGeocodeData,
    ToolError,
    ToolRegistry,
    ToolResult,
    create_default_registry,
)

__all__ = [
    "AreaOsmAnalysisData",
    "GeocodeData",
    "NearbySearchData",
    "OsmBlockName",
    "OsmTools",
    "PolygonSearchData",
    "ReverseGeocodeData",
    "ToolError",
    "ToolRegistry",
    "ToolResult",
    "create_default_registry",
]

__version__ = "0.4.0"
