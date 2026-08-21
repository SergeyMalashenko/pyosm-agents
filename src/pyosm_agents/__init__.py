"""Agent-safe tools for OpenStreetMap services."""

from .core import (
    GeocodeData,
    NearbySearchData,
    OsmTools,
    ReverseGeocodeData,
    ToolError,
    ToolRegistry,
    ToolResult,
    create_default_registry,
)

__all__ = [
    "GeocodeData",
    "NearbySearchData",
    "OsmTools",
    "ReverseGeocodeData",
    "ToolError",
    "ToolRegistry",
    "ToolResult",
    "create_default_registry",
]

__version__ = "0.1.0"
