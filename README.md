# pyosm-agents

`pyosm-agents` exposes a small, predictable set of OpenStreetMap operations to
LLM agents. It includes a framework-neutral Python API and an MCP server for
Hermes, MCP Inspector, and other compatible clients. Land parcels can be
addressed directly by cadastral number: the server resolves their contours with
`pynspd` and analyzes OpenStreetMap data locally.

## MCP tools

| Tool | Purpose | Upstream service |
|---|---|---|
| `osm_geocode` | Find coordinates and OSM objects by an address or place name | Nominatim |
| `osm_reverse_geocode` | Describe a place or address at WGS84 coordinates | Nominatim |
| `osm_search_nearby` | Find nodes, ways, and relations near coordinates by exact OSM tags | Overpass API |
| `osm_search_in_polygon` | Find tagged OSM objects in a GeoJSON contour and verify exact relations locally | Overpass API |
| `osm_analyze_land_parcel` | Resolve an NSPD parcel by cadastral number and analyze thematic OSM blocks | NSPD + Overpass API |

`osm_search_nearby` does not accept arbitrary Overpass QL. It accepts one to
five exact tags, a radius of at most 5 km, and a result limit of at most 100. The
server builds and escapes the query itself.

`osm_search_in_polygon` and `osm_analyze_land_parcel` use the parcel bounding
box in Overpass only to retrieve candidates efficiently. Points, lines,
polygons, and supported
multipolygon relations are then checked against the original contour with
Shapely in a local metric projection. Boundary-only contact is excluded.

The cadastral tool exposes five stable blocks:

| Block | Representative OSM tag keys |
|---|---|
| `buildings` | `building`, `building:part` |
| `transport` | `highway`, `railway`, `public_transport`, `aeroway`, `waterway` |
| `landuse` | `landuse`, `natural`, `leisure` |
| `infrastructure` | `power`, `man_made`, `utility`, `telecom`, `pipeline` |
| `poi` | `amenity`, `shop`, `tourism`, `office`, `craft`, `healthcare`, `emergency` |

Each result has one of four exclusive relationships:
`no_intersection`, `intersection`, `object_inside_parcel`, or
`parcel_inside_object`. Only the latter three are returned as matches.

The composite tool calls `pynspd` in-process; it does not call or require a
separate `pynspd-mcp` process. Keeping `pynspd-http` enabled in Hermes remains
useful for NSPD-specific parcel attributes and regulatory layers.

All successful tool responses use the same envelope:

```json
{
  "ok": true,
  "data": {},
  "error": null,
  "metadata": {
    "provider": "Nominatim",
    "attribution": "© OpenStreetMap contributors",
    "license": "Open Data Commons Open Database License (ODbL)",
    "license_url": "https://www.openstreetmap.org/copyright"
  }
}
```

## Installation

From a clone of this repository:

```bash
python -m pip install -e '.[mcp]'
```

The default public services can be replaced without changing the agent:

```bash
export PYOSM_NOMINATIM_URL=https://nominatim.example.org
export PYOSM_OVERPASS_URL=https://overpass.example.org/api/interpreter
export PYOSM_USER_AGENT='my-osm-agent/1.0 (+https://example.org/contact)'
export PYOSM_CONTACT_EMAIL=osm@example.org
```

`PYOSM_CONTACT_EMAIL` is optional. Set a descriptive `PYOSM_USER_AGENT` that
identifies your deployment. The defaults identify this project.

## Run the MCP server

Streamable HTTP on port 8002 (port 8001 can remain assigned to `pynspd-mcp`):

```bash
pyosm-mcp --transport streamable-http --host 127.0.0.1 --port 8002
```

Stateless HTTP is the default. The server keeps its shared rate limiter, cache,
and upstream clients alive across MCP requests and closes them when the server
process stops. Unexpected implementation errors are logged with a traceback on
the server while clients receive the stable `internal_error` envelope.

Or let an MCP client start one stdio process itself:

```bash
pyosm-mcp --transport stdio
```

Test discovery with MCP Inspector:

```bash
npx -y @modelcontextprotocol/inspector \
  --cli http://127.0.0.1:8002/mcp \
  --transport http \
  --method tools/list
```

Example tool calls:

```bash
npx -y @modelcontextprotocol/inspector \
  --cli http://127.0.0.1:8002/mcp \
  --transport http \
  --method tools/call \
  --tool-name osm_geocode \
  --tool-arg 'query=Нижний Новгород, Кремль' \
  --tool-arg 'country_codes=["ru"]'

npx -y @modelcontextprotocol/inspector \
  --cli http://127.0.0.1:8002/mcp \
  --transport http \
  --method tools/call \
  --tool-name osm_search_nearby \
  --tool-arg 'latitude=56.3287' \
  --tool-arg 'longitude=44.0020' \
  --tool-arg 'radius_m=1000' \
  --tool-arg 'tags={"amenity":"hospital"}'

npx -y @modelcontextprotocol/inspector \
  --cli http://127.0.0.1:8002/mcp \
  --transport http \
  --method tools/call \
  --tool-name osm_analyze_land_parcel \
  --tool-args-json '{
    "cadastral_number":"52:24:0000000:2216",
    "blocks":["buildings","transport","landuse","infrastructure","poi"],
    "limit_per_block":25,
    "include_geometry":false
  }'
```

For Hermes, register `http://127.0.0.1:8002/mcp` as an HTTP MCP server named,
for example, `pyosm-http`, then verify it with:

```bash
hermes mcp test pyosm-http
```

## Public-service constraints

The public Nominatim service is intended for moderate, user-triggered requests.
This package serializes its Nominatim requests at one request per second and
caches repeated requests in memory. Do not use the public endpoint for bulk
geocoding, autocomplete, systematic scanning, or data extraction. Deploy your
own Nominatim and/or Overpass instances for sustained workloads.

Polygon requests are capped at 500 km². High-level parcel analysis requests at
most 500 Overpass candidates and reports `global_limit_reached` when
completeness cannot be guaranteed. These limits protect public endpoints; a
self-hosted deployment can raise them in a future configuration extension.

See the [Nominatim Usage Policy](https://operations.osmfoundation.org/policies/nominatim/),
the [Nominatim API documentation](https://nominatim.org/release-docs/latest/api/Overview/),
and the [Overpass QL documentation](https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL).

OpenStreetMap data is community-maintained and can be incomplete. Preserve the
required OpenStreetMap attribution in user-visible results.
