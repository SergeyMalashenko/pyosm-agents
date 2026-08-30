# pyosm-agents

`pyosm-agents` exposes bounded OpenStreetMap and Nominatim operations through a
framework-neutral Python API and an MCP server. The package is independent from
NSPD: it accepts WGS84 coordinates or GeoJSON and never resolves cadastral
numbers itself.

## MCP tools

| Tool | Purpose | Upstream |
|---|---|---|
| `osm_geocode` | Find coordinates and OSM objects by an address or place name | Nominatim |
| `osm_reverse_geocode` | Describe a place or address at WGS84 coordinates | Nominatim |
| `osm_search_nearby` | Find objects near coordinates by exact OSM tags | Overpass API |
| `osm_search_in_polygon` | Find tagged objects intersecting an exact GeoJSON contour | Overpass API |
| `osm_analyze_area` | Collect forests, lakes, rivers, streams, and roads in an expanded circle | Overpass API |

Arbitrary Overpass QL is not accepted. The server generates bounded queries and
preserves the required OpenStreetMap attribution.

## Circular area analysis

`osm_analyze_area` accepts a Polygon or MultiPolygon in `EPSG:4326`. It:

1. validates and repairs the contour with Shapely;
2. transforms it to a local Lambert azimuthal equal-area projection;
3. calculates the minimum circle containing the complete contour;
4. adds `margin_m`, which defaults to 1000 metres, to the minimum radius;
5. requests candidates using the circle's bounding box;
6. reconstructs node, way, and relation geometries;
7. retains objects that are inside or intersect the exact circle;
8. calculates every object's distance and relation to the original contour;
9. groups objects into stable thematic blocks.

The five blocks are:

| Block | Exact OSM classification | Geometry |
|---|---|---|
| `forests` | `natural=wood` or `landuse=forest` | Polygon/MultiPolygon contour |
| `lakes` | `natural=water` and `water=lake` | Polygon/MultiPolygon contour |
| `rivers` | `natural=water` and `water=river`, or `waterway=riverbank` | Polygon/MultiPolygon contour |
| `streams` | `waterway=stream` | LineString/MultiLineString |
| `roads` | selected drivable and service `highway` values | LineString/MultiLineString |

Forest, lake, and river GeoJSON is always included, even when
`include_geometry=false`. Multipolygon interior rings are preserved, so islands,
clearings, and other holes remain part of the contour semantics. Streams and roads
are returned as linear geometry when `include_geometry=true`.

The result includes:

- a summary of the input contour;
- the search centre, minimum parcel radius, margin, final radius, bbox, and
  search-area GeoJSON;
- candidate and discarded counts;
- block completeness flags;
- normalized OSM objects with tags, URL, optional geometry,
  `distance_to_parcel_m`, relation to the parcel, and relation to the search
  area.

Objects outside the parcel normally have `relation.kind=no_intersection` but
remain in the result when they fall inside the expanded search circle. Linear
objects crossing the circle are returned with
`search_relation=intersects_search_area`.

## Framework-neutral use

```python
import asyncio

from pyosm_agents import OsmTools


PARCEL = {
    "type": "Polygon",
    "coordinates": [
        [
            [44.0018, 56.3286],
            [44.0024, 56.3286],
            [44.0024, 56.3291],
            [44.0018, 56.3291],
            [44.0018, 56.3286],
        ]
    ],
}


async def main() -> None:
    async with OsmTools() as tools:
        result = await tools.analyze_area(
            PARCEL,
            margin_m=1000,
            blocks=[
                "forests",
                "lakes",
                "rivers",
                "streams",
                "roads",
            ],
            limit_per_block=100,
            include_geometry=True,
        )
        print(result.model_dump_json(indent=2))


asyncio.run(main())
```

## Installation and server

```bash
python -m pip install -e '.[mcp]'
pyosm-mcp --transport streamable-http --host 127.0.0.1 --port 8002
```

The endpoint is `http://127.0.0.1:8002/mcp`. Stateless Streamable HTTP with JSON
responses is the default.

Test discovery:

```bash
npx -y @modelcontextprotocol/inspector \
  --cli http://127.0.0.1:8002/mcp \
  --transport http \
  --method tools/list
```

Example area call:

```bash
npx -y @modelcontextprotocol/inspector \
  --cli http://127.0.0.1:8002/mcp \
  --transport http \
  --method tools/call \
  --tool-name osm_analyze_area \
  --tool-args-json '{
    "geometry": {
      "type": "Polygon",
      "coordinates": [[[44.0018,56.3286],[44.0024,56.3286],[44.0024,56.3291],[44.0018,56.3291],[44.0018,56.3286]]]
    },
    "source_crs": "EPSG:4326",
    "margin_m": 1000,
    "blocks": ["forests","lakes","rivers","streams","roads"],
    "limit_per_block": 100,
    "include_geometry": true
  }'
```

## Configuration

```bash
export PYOSM_NOMINATIM_URL=https://nominatim.example.org
export PYOSM_OVERPASS_URL=https://overpass.example.org/api/interpreter
export PYOSM_USER_AGENT='my-osm-agent/1.0 (+https://example.org/contact)'
export PYOSM_CONTACT_EMAIL=osm@example.org
```

Public-service calls remain bounded. Polygonal search areas are limited to
500 km² and the thematic request uses a global candidate cap of 500. When a cap
is reached, the result sets completeness flags and emits a warning instead of
claiming that the returned set is exhaustive. A self-hosted Overpass deployment
can support higher limits in a future configuration extension.

OpenStreetMap data is community-maintained and may be incomplete or outdated.
Preserve `© OpenStreetMap contributors` and the ODbL attribution in user-visible
outputs.
