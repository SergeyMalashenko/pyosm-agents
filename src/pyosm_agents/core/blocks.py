"""Stable, semantically filtered blocks used by parcel-area analysis."""

from __future__ import annotations

from collections.abc import Mapping

from .schemas import OsmBlockName

AREAL_OSM_BLOCKS: frozenset[OsmBlockName] = frozenset(
    {"forests", "lakes", "rivers"}
)
LINEAR_OSM_BLOCKS: frozenset[OsmBlockName] = frozenset({"streams", "roads"})

ROAD_HIGHWAY_VALUES = frozenset(
    {
        "motorway",
        "trunk",
        "primary",
        "secondary",
        "tertiary",
        "unclassified",
        "residential",
        "living_street",
        "service",
        "track",
    }
)

# ``natural=water`` is valid on its own.  Keep the public ``lakes`` block name
# stable, but treat it as the standing/unspecified waterbody block so mapped
# ponds, reservoirs, flooded quarries, and legacy untyped water areas are not
# silently discarded.  Flowing water remains in the dedicated river block.
STANDING_WATER_VALUES = frozenset(
    {
        "basin",
        "lagoon",
        "lake",
        "oxbow",
        "pond",
        "reservoir",
    }
)

OSM_BLOCK_FILTERS: dict[OsmBlockName, tuple[dict[str, str], ...]] = {
    "forests": (
        {"natural": "wood"},
        {"landuse": "forest"},
    ),
    "lakes": ({"natural": "water"},),
    "rivers": (
        {"natural": "water", "water": "river"},
        {"waterway": "riverbank"},
    ),
    "streams": ({"waterway": "stream"},),
    "roads": tuple(
        {"highway": value} for value in sorted(ROAD_HIGHWAY_VALUES)
    ),
}

# These expressions explain the active query in every block response.
OSM_BLOCK_TAG_KEYS: dict[OsmBlockName, tuple[str, ...]] = {
    "forests": ("natural=wood", "landuse=forest"),
    "lakes": ("natural=water + water absent or standing-water type",),
    "rivers": ("natural=water + water=river", "waterway=riverbank"),
    "streams": ("waterway=stream",),
    "roads": tuple(
        f"highway={value}" for value in sorted(ROAD_HIGHWAY_VALUES)
    ),
}


def tag_filters_for_blocks(
    blocks: list[OsmBlockName],
) -> list[dict[str, str]]:
    """Return unique OR-ed exact filters for the selected semantic blocks."""

    filters: list[dict[str, str]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for block in blocks:
        for tag_filter in OSM_BLOCK_FILTERS[block]:
            identity = tuple(sorted(tag_filter.items()))
            if identity not in seen:
                seen.add(identity)
                filters.append(dict(tag_filter))
    return filters


def blocks_for_tags(
    tags: Mapping[str, str],
    selected_blocks: list[OsmBlockName],
) -> list[OsmBlockName]:
    """Classify tags into stable semantic blocks after the broad OSM query."""

    def matches(block: OsmBlockName) -> bool:
        if block == "lakes":
            if tags.get("natural") != "water":
                return False
            water_type = tags.get("water")
            return water_type is None or water_type in STANDING_WATER_VALUES
        return any(
            all(tags.get(key) == value for key, value in tag_filter.items())
            for tag_filter in OSM_BLOCK_FILTERS[block]
        )

    return [
        block
        for block in selected_blocks
        if matches(block)
    ]


def block_accepts_geometry(block: OsmBlockName, geometry_type: str) -> bool:
    """Enforce contours for natural areas and lines for roads and streams."""

    if block in AREAL_OSM_BLOCKS:
        return geometry_type in {"Polygon", "MultiPolygon"}
    if block in LINEAR_OSM_BLOCKS:
        return geometry_type in {"LineString", "MultiLineString"}
    return False
