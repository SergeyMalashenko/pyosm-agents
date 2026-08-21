"""Pydantic contracts shared by the MCP server and future adapters."""

from __future__ import annotations

import re
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

T = TypeVar("T")
OsmElementType = Literal["node", "way", "relation"]
OsmBlockName = Literal[
    "buildings",
    "transport",
    "landuse",
    "infrastructure",
    "poi",
]
SpatialRelationKind = Literal[
    "no_intersection",
    "intersection",
    "object_inside_parcel",
    "parcel_inside_object",
]

TAG_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_:.-]+$")
COUNTRY_CODE_PATTERN = re.compile(r"^[A-Za-z]{2}$")
CADASTRAL_NUMBER_PATTERN = re.compile(r"^\d+:\d+:\d+:\d+$")


def _default_osm_blocks() -> list[OsmBlockName]:
    return ["buildings", "transport", "landuse", "infrastructure", "poi"]


class ToolError(BaseModel):
    """Stable, agent-friendly representation of an execution error."""

    code: str
    message: str
    retryable: bool = False


class ToolResult(BaseModel, Generic[T]):
    """Common result envelope returned by every OpenStreetMap tool."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    data: T | None = None
    error: ToolError | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_result_state(self) -> ToolResult[T]:
        if self.ok and self.error is not None:
            raise ValueError("A successful result cannot contain an error")
        if not self.ok and self.error is None:
            raise ValueError("A failed result must contain an error")
        return self

    @classmethod
    def success(
        cls,
        data: T,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult[T]:
        return cls(ok=True, data=data, metadata=metadata or {})

    @classmethod
    def failure(
        cls,
        error: ToolError,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult[T]:
        return cls(ok=False, error=error, metadata=metadata or {})


class GeocodeInput(BaseModel):
    """Arguments for forward geocoding with Nominatim."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=2, max_length=500)
    limit: int = Field(default=5, ge=1, le=10)
    country_codes: list[str] = Field(default_factory=list, max_length=10)
    language: str = Field(default="ru", min_length=1, max_length=100)
    include_geometry: bool = False

    @field_validator("query", "language", mode="before")
    @classmethod
    def strip_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("country_codes")
    @classmethod
    def normalize_country_codes(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for code in value:
            code = code.strip().lower()
            if not COUNTRY_CODE_PATTERN.fullmatch(code):
                raise ValueError("Country codes must contain exactly two letters")
            if code not in normalized:
                normalized.append(code)
        return normalized


class ReverseGeocodeInput(BaseModel):
    """Arguments for reverse geocoding with Nominatim."""

    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    zoom: int = Field(default=18, ge=0, le=18)
    language: str = Field(default="ru", min_length=1, max_length=100)
    include_geometry: bool = False

    @field_validator("language", mode="before")
    @classmethod
    def strip_language(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class NearbySearchInput(BaseModel):
    """Arguments for a bounded, generated Overpass query."""

    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_m: int = Field(default=500, ge=1, le=5000)
    tags: dict[str, str | None] = Field(min_length=1, max_length=5)
    limit: int = Field(default=20, ge=1, le=100)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: dict[str, str | None]) -> dict[str, str | None]:
        normalized: dict[str, str | None] = {}
        for key, tag_value in value.items():
            key = key.strip()
            if not TAG_KEY_PATTERN.fullmatch(key):
                raise ValueError(
                    "Tag keys may contain only letters, digits, '_', ':', '.', or '-'"
                )
            if tag_value is not None:
                tag_value = tag_value.strip()
                if not tag_value:
                    raise ValueError(
                        "Tag values cannot be empty; use null for any value"
                    )
                if len(tag_value) > 200:
                    raise ValueError("Tag values cannot exceed 200 characters")
            normalized[key] = tag_value
        return normalized


class PolygonSearchInput(BaseModel):
    """Arguments for exact OSM search against a GeoJSON polygon."""

    model_config = ConfigDict(extra="forbid")

    geometry: dict[str, Any] = Field(
        description="WGS84 GeoJSON Polygon or MultiPolygon"
    )
    tags: dict[str, str | None] = Field(min_length=1, max_length=5)
    limit: int = Field(default=100, ge=1, le=500)
    include_geometry: bool = False

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: dict[str, str | None]) -> dict[str, str | None]:
        return NearbySearchInput.validate_tags(value)


class AnalyzeLandParcelInput(BaseModel):
    """Arguments for thematic OSM analysis of one EGRN land parcel."""

    model_config = ConfigDict(extra="forbid")

    cadastral_number: str = Field(
        description="Cadastral number in the form 77:05:0001005:19"
    )
    blocks: list[OsmBlockName] = Field(
        default_factory=_default_osm_blocks,
        min_length=1,
        description=(
            "OSM blocks: buildings, transport, landuse, infrastructure, or poi"
        ),
    )
    limit_per_block: int = Field(default=50, ge=1, le=100)
    include_geometry: bool = False

    @field_validator("cadastral_number", mode="before")
    @classmethod
    def normalize_cadastral_number(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise TypeError("Cadastral number must be a string")
        normalized = re.sub(r"\s+", "", value)
        if not CADASTRAL_NUMBER_PATTERN.fullmatch(normalized):
            raise ValueError(
                "Cadastral number must contain four numeric parts separated by ':'"
            )
        return normalized

    @field_validator("blocks")
    @classmethod
    def unique_blocks(cls, value: list[OsmBlockName]) -> list[OsmBlockName]:
        return list(dict.fromkeys(value))


class GeocodingResult(BaseModel):
    """One normalized Nominatim place."""

    place_id: int | None = None
    osm_type: OsmElementType | None = None
    osm_id: int | None = None
    display_name: str
    name: str | None = None
    latitude: float
    longitude: float
    bounding_box: tuple[float, float, float, float] | None = None
    category: str | None = None
    type: str | None = None
    importance: float | None = None
    address: dict[str, str] = Field(default_factory=dict)
    geojson: dict[str, Any] | None = None
    osm_url: str | None = None


class GeocodeData(BaseModel):
    """Normalized results of one forward-geocoding request."""

    query: str
    results: list[GeocodingResult]


class ReverseGeocodeData(BaseModel):
    """Normalized result of one reverse-geocoding request."""

    requested_latitude: float
    requested_longitude: float
    result: GeocodingResult


class NearbyFeature(BaseModel):
    """One OpenStreetMap element returned by a bounded nearby search."""

    element_type: OsmElementType
    osm_id: int
    name: str | None = None
    latitude: float
    longitude: float
    distance_m: float
    tags: dict[str, str] = Field(default_factory=dict)
    osm_url: str


class NearbySearchData(BaseModel):
    """Normalized result of a generated Overpass query."""

    latitude: float
    longitude: float
    radius_m: int
    tags: dict[str, str | None]
    returned_count: int
    limit_reached: bool
    features: list[NearbyFeature]


class GeometrySummary(BaseModel):
    """Compact WGS84 and metric summary of an analysis geometry."""

    type: str
    bbox: tuple[float, float, float, float]
    centroid: tuple[float, float]
    area_m2: float


class SpatialRelationData(BaseModel):
    """Exact local relationship between an OSM object and the parcel."""

    kind: SpatialRelationKind
    intersection_area_m2: float = 0.0
    intersection_length_m: float = 0.0
    parcel_coverage_percent: float = 0.0
    object_coverage_percent: float = 0.0


class OsmSpatialFeature(BaseModel):
    """One geometrically classified OpenStreetMap element."""

    element_type: OsmElementType
    osm_id: int
    blocks: list[OsmBlockName] = Field(default_factory=list)
    name: str | None = None
    geometry_type: str
    latitude: float
    longitude: float
    relation: SpatialRelationData
    tags: dict[str, str] = Field(default_factory=dict)
    osm_url: str
    geojson: dict[str, Any] | None = None


class PolygonSearchData(BaseModel):
    """Exact search results for one caller-provided polygon."""

    contour: GeometrySummary
    tags: dict[str, str | None]
    candidate_count: int
    discarded_candidate_count: int
    returned_count: int
    limit_reached: bool
    features: list[OsmSpatialFeature]


class LandParcelSummary(BaseModel):
    """Minimal parcel information attached to an OSM analysis."""

    cadastral_number: str
    address: str | None = None
    declared_area_m2: float | None = None
    geometry: GeometrySummary


class OsmBlockResult(BaseModel):
    """Results for one thematic OSM tag block."""

    block: OsmBlockName
    tag_keys: list[str]
    returned_count: int
    limit_reached: bool
    features: list[OsmSpatialFeature]


class LandParcelOsmAnalysisData(BaseModel):
    """Combined NSPD parcel and exact OSM spatial analysis."""

    parcel: LandParcelSummary
    candidate_count: int
    discarded_candidate_count: int
    global_limit_reached: bool
    blocks: list[OsmBlockResult]
    warnings: list[str] = Field(default_factory=list)
