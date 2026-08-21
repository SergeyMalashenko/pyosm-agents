"""Framework-neutral OpenStreetMap tool contracts and implementation."""

from .client import OsmClient, OsmHttpClient
from .registry import ToolDefinition, ToolRegistry, create_default_registry
from .schemas import (
    GeocodeData,
    GeocodeInput,
    GeocodingResult,
    NearbyFeature,
    NearbySearchData,
    NearbySearchInput,
    ReverseGeocodeData,
    ReverseGeocodeInput,
    ToolError,
    ToolResult,
)
from .tools import OsmTools

__all__ = [
    "GeocodeData",
    "GeocodeInput",
    "GeocodingResult",
    "NearbyFeature",
    "NearbySearchData",
    "NearbySearchInput",
    "OsmClient",
    "OsmHttpClient",
    "OsmTools",
    "ReverseGeocodeData",
    "ReverseGeocodeInput",
    "ToolDefinition",
    "ToolError",
    "ToolRegistry",
    "ToolResult",
    "create_default_registry",
]
