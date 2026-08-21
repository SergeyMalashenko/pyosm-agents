"""Stable thematic blocks used by land-parcel OSM analysis."""

from __future__ import annotations

from .schemas import OsmBlockName

OSM_BLOCK_TAG_KEYS: dict[OsmBlockName, tuple[str, ...]] = {
    "buildings": ("building", "building:part"),
    "transport": (
        "highway",
        "railway",
        "public_transport",
        "aeroway",
        "waterway",
    ),
    "landuse": ("landuse", "natural", "leisure"),
    "infrastructure": (
        "power",
        "man_made",
        "utility",
        "telecom",
        "pipeline",
    ),
    "poi": (
        "amenity",
        "shop",
        "tourism",
        "office",
        "craft",
        "healthcare",
        "emergency",
    ),
}


def tag_filters_for_blocks(
    blocks: list[OsmBlockName],
) -> list[dict[str, None]]:
    """Return unique OR-ed has-key filters for thematic blocks."""

    keys = dict.fromkeys(key for block in blocks for key in OSM_BLOCK_TAG_KEYS[block])
    return [{key: None} for key in keys]


def blocks_for_tags(
    tags: dict[str, str],
    selected_blocks: list[OsmBlockName],
) -> list[OsmBlockName]:
    """Classify one OSM tag dictionary into selected thematic blocks."""

    return [
        block
        for block in selected_blocks
        if any(key in tags for key in OSM_BLOCK_TAG_KEYS[block])
    ]
