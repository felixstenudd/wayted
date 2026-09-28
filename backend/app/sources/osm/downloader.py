"""Fetches one or more OSM layers in a single Overpass request and stores the raw elements."""

from collections.abc import Sequence

import httpx
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg.types.json import Jsonb

from ..tiles import Bounds
from .layers import OsmLayer
from .overpass import OsmData, build_query, run_query

# Unchanged rows are left alone, so a refresh of unchanged data writes nothing and a row's xmin
# shows when its content last changed.
UPSERT_NODE = """
    INSERT INTO raw.osm_nodes AS existing (id, tags, geom)
    VALUES (%(id)s, %(tags)s, ST_Point(%(lon)s, %(lat)s, 4326))
    ON CONFLICT (id) DO UPDATE SET tags = EXCLUDED.tags, geom = EXCLUDED.geom
    WHERE (existing.tags, existing.geom) IS DISTINCT FROM (EXCLUDED.tags, EXCLUDED.geom)
"""

UPSERT_WAY = """
    INSERT INTO raw.osm_ways AS existing (id, tags, node_ids)
    VALUES (%(id)s, %(tags)s, %(node_ids)s)
    ON CONFLICT (id) DO UPDATE SET tags = EXCLUDED.tags, node_ids = EXCLUDED.node_ids
    WHERE (existing.tags, existing.node_ids) IS DISTINCT FROM (EXCLUDED.tags, EXCLUDED.node_ids)
"""

UPSERT_RELATION = """
    INSERT INTO raw.osm_relations AS existing (id, tags, members)
    VALUES (%(id)s, %(tags)s, %(members)s)
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

    async def fetch(self, bounds: Bounds) -> OsmData:
        query = build_query(
            self.selectors,
            bounds,
            enclosing_selectors=self.enclosing_selectors,
            shallow_selectors=self.shallow_selectors,
        )
        return await run_query(self.client, query)

    async def store(self, conn: AsyncConnection[TupleRow], payload: OsmData) -> None:
        nodes = sorted(payload.nodes, key=lambda n: n.id)
        ways = sorted(payload.ways, key=lambda w: w.id)
        relations = sorted(payload.relations, key=lambda r: r.id)
        async with conn.cursor() as cur:
            await cur.executemany(
                UPSERT_NODE,
                [{"id": n.id, "tags": Jsonb(n.tags), "lon": n.lon, "lat": n.lat} for n in nodes],
            )
            await cur.executemany(
                UPSERT_WAY,
                [{"id": w.id, "tags": Jsonb(w.tags), "node_ids": w.node_ids} for w in ways],
            )
            await cur.executemany(
                UPSERT_RELATION,
                [
                    {
                        "id": r.id,
                        "tags": Jsonb(r.tags),
                        "members": Jsonb(
                            [{"type": m.type, "ref": m.ref, "role": m.role} for m in r.members]
                        ),
                    }
                    for r in relations
                ],
            )
