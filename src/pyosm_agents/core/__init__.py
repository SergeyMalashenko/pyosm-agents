"""Framework-neutral OpenStreetMap tool contracts and implementation."""

from .client import OsmClient, OsmHttpClient
from .registry import ToolDefinition, ToolRegistry, create_default_registry
from .schemas import (
    AnalyzeAreaInput,
    AreaOsmAnalysisData,
    GeocodeData,
    GeocodeInput,
    GeocodingResult,
    NearbyFeature,
    NearbySearchData,
    NearbySearchInput,
    OsmBlockName,
    OsmSpatialFeature,
    PolygonSearchData,
    PolygonSearchInput,
    ReverseGeocodeData,
    ReverseGeocodeInput,
    SearchAreaSummary,
    ToolError,
    ToolResult,
)
from .tools import OsmTools

__all__ = [
    "AnalyzeAreaInput",
    "AreaOsmAnalysisData",
    "GeocodeData",
    "GeocodeInput",
    "GeocodingResult",
    "NearbyFeature",
    "NearbySearchData",
    "NearbySearchInput",
    "OsmBlockName",
    "OsmClient",
    "OsmHttpClient",
    "OsmSpatialFeature",
    "OsmTools",
    "PolygonSearchData",
    "PolygonSearchInput",
    "ReverseGeocodeData",
    "ReverseGeocodeInput",
    "SearchAreaSummary",
    "ToolDefinition",
    "ToolError",
    "ToolRegistry",
    "ToolResult",
    "create_default_registry",
]
