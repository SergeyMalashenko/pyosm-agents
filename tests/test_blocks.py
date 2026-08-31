from __future__ import annotations

from pyosm_agents.core.blocks import (
    block_accepts_geometry,
    blocks_for_tags,
    tag_filters_for_blocks,
)


def test_exact_block_filters_are_generated_without_broad_highway_query() -> None:
    filters = tag_filters_for_blocks(
        ["forests", "lakes", "rivers", "streams", "roads"]
    )

    assert {"natural": "wood"} in filters
    assert {"natural": "water"} in filters
    assert {"natural": "water", "water": "river"} in filters
    assert {"waterway": "stream"} in filters
    assert {"highway": "secondary"} in filters
    assert {"highway": "street_lamp"} not in filters


def test_semantic_blocks_reject_unrelated_highway_points() -> None:
    selected = ["forests", "lakes", "rivers", "streams", "roads"]

    assert blocks_for_tags({"highway": "secondary"}, selected) == ["roads"]
    assert blocks_for_tags({"highway": "street_lamp"}, selected) == []
    assert blocks_for_tags(
        {"natural": "water", "water": "river"}, selected
    ) == ["rivers"]
    assert blocks_for_tags(
        {"natural": "water", "name": "Дракинский карьер"}, selected
    ) == ["lakes"]
    assert blocks_for_tags(
        {"natural": "water", "water": "reservoir"}, selected
    ) == ["lakes"]
    assert blocks_for_tags(
        {"natural": "water", "water": "canal"}, selected
    ) == []
    assert block_accepts_geometry("rivers", "Polygon")
    assert not block_accepts_geometry("rivers", "LineString")
    assert block_accepts_geometry("streams", "LineString")
