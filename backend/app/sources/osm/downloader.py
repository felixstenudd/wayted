"""Fetches one or more OSM layers in a single Overpass request and stores the raw elements."""

from collections.abc import Sequence

import httpx
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg.types.json import Jsonb

from ..tiles import Bounds
from .layers import OsmLayer
from .overpass import OsmData, build_query, run_query

CREATE_INCOMING = """
    CREATE TEMP TABLE incoming_nodes (id bigint, tags jsonb, lon float8, lat float8) ON COMMIT DROP;
    CREATE TEMP TABLE incoming_ways (id bigint, tags jsonb, node_ids bigint[]) ON COMMIT DROP;
    CREATE TEMP TABLE incoming_relations (id bigint, tags jsonb, members jsonb) ON COMMIT DROP
"""

# Unchanged rows are left alone, so a refresh of unchanged data writes nothing and a row's xmin
# shows when its content last changed. Rows go in id order so concurrent stores lock alike, and
# once each: one statement cannot update a row twice.
UPSERT_NODES = """
    INSERT INTO raw.osm_nodes AS existing (id, tags, geom)
    SELECT DISTINCT ON (id) id, tags, ST_Point(lon, lat, 4326) FROM incoming_nodes ORDER BY id
    ON CONFLICT (id) DO UPDATE SET tags = EXCLUDED.tags, geom = EXCLUDED.geom
    WHERE (existing.tags, existing.geom) IS DISTINCT FROM (EXCLUDED.tags, EXCLUDED.geom)
"""

UPSERT_WAYS = """
    INSERT INTO raw.osm_ways AS existing (id, tags, node_ids)
    SELECT DISTINCT ON (id) id, tags, node_ids FROM incoming_ways ORDER BY id
    ON CONFLICT (id) DO UPDATE SET tags = EXCLUDED.tags, node_ids = EXCLUDED.node_ids
    WHERE (existing.tags, existing.node_ids) IS DISTINCT FROM (EXCLUDED.tags, EXCLUDED.node_ids)
"""

UPSERT_RELATIONS = """
    INSERT INTO raw.osm_relations AS existing (id, tags, members)
    SELECT DISTINCT ON (id) id, tags, members FROM incoming_relations ORDER BY id
    ON CONFLICT (id) DO UPDATE SET tags = EXCLUDED.tags, members = EXCLUDED.members
    WHERE (existing.tags, existing.members) IS DISTINCT FROM (EXCLUDED.tags, EXCLUDED.members)
"""


class OsmDownloader:
    def __init__(
        self,
        client: httpx.AsyncClient,
        layers: Sequence[OsmLayer],
        max_tiles: int = 64,
        max_extra_tiles: int = 16,
        max_requests: int = 2,
    ) -> None:
        self.client = client
        self.layers = tuple(layer.code for layer in layers)
        self.selectors = [selector for layer in layers for selector in layer.selectors]
        self.enclosing_selectors = [
            selector for layer in layers if layer.is_area for selector in layer.selectors
        ]
        self.shallow_selectors = [
            selector for layer in layers for selector in layer.shallow_selectors
        ]
        self.max_tiles = max_tiles
        self.max_extra_tiles = max_extra_tiles
        # The public Overpass instance runs two queries at a time per IP address.
        self.max_requests = max_requests

    async def fetch(self, bounds: Bounds) -> OsmData:
        query = build_query(
            self.selectors,
            bounds,
            enclosing_selectors=self.enclosing_selectors,
            shallow_selectors=self.shallow_selectors,
        )
        return await run_query(self.client, query)

    async def store(self, conn: AsyncConnection[TupleRow], payload: OsmData) -> None:
        """Copy the elements into work tables, then upsert each table in one statement."""
        await conn.execute(CREATE_INCOMING)
        async with conn.cursor() as cur:
            async with cur.copy("COPY incoming_nodes FROM STDIN") as copy:
                for n in payload.nodes:
                    await copy.write_row((n.id, Jsonb(n.tags), n.lon, n.lat))
            async with cur.copy("COPY incoming_ways FROM STDIN") as copy:
                for w in payload.ways:
                    await copy.write_row((w.id, Jsonb(w.tags), w.node_ids))
            async with cur.copy("COPY incoming_relations FROM STDIN") as copy:
                for r in payload.relations:
                    members = [{"type": m.type, "ref": m.ref, "role": m.role} for m in r.members]
                    await copy.write_row((r.id, Jsonb(r.tags), Jsonb(members)))
            for upsert in (UPSERT_NODES, UPSERT_WAYS, UPSERT_RELATIONS):
                await cur.execute(upsert)
