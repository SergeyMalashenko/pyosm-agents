# pyosm-agents

`pyosm-agents` exposes a small, predictable set of OpenStreetMap operations to
LLM agents. The first release includes a framework-neutral Python API and an MCP
server for Hermes, MCP Inspector, and other compatible clients.

## MCP tools

| Tool | Purpose | Upstream service |
|---|---|---|
| `osm_geocode` | Find coordinates and OSM objects by an address or place name | Nominatim |
| `osm_reverse_geocode` | Describe a place or address at WGS84 coordinates | Nominatim |
| `osm_search_nearby` | Find nodes, ways, and relations near coordinates by exact OSM tags | Overpass API |

`osm_search_nearby` does not accept arbitrary Overpass QL. It accepts one to
five exact tags, a radius of at most 5 km, and a result limit of at most 100. The
server builds and escapes the query itself.

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

See the [Nominatim Usage Policy](https://operations.osmfoundation.org/policies/nominatim/),
the [Nominatim API documentation](https://nominatim.org/release-docs/latest/api/Overview/),
and the [Overpass QL documentation](https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL).

OpenStreetMap data is community-maintained and can be incomplete. Preserve the
required OpenStreetMap attribution in user-visible results.
