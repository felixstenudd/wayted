"""
Queue every edge for scoring again, and with --features every feature for rebuilding, after a
layer or attribute definition changed.
"""

import argparse
import asyncio
from collections.abc import Sequence

from psycopg import AsyncConnection
from psycopg.conninfo import make_conninfo
from psycopg.rows import TupleRow
from psycopg.types.json import Jsonb

from .definitions import LAYERS

REQUEUE_EDGES = "INSERT INTO graph.pending_edges (edge_id) SELECT id FROM graph.edges"

# What matches a layer now, and what was built under the old definition.
REQUEUE_WAYS = """
    INSERT INTO enrich.pending_ways (way_id)
    SELECT id FROM raw.osm_ways WHERE tags @> ANY(%(match)s::jsonb[])
    UNION SELECT osm_id FROM enrich.areas WHERE osm_type = 'way'
    UNION SELECT osm_id FROM enrich.lines
"""

REQUEUE_RELATIONS = """
    INSERT INTO enrich.pending_relations (relation_id)
    SELECT id FROM raw.osm_relations WHERE tags @> ANY(%(match)s::jsonb[])
    UNION SELECT osm_id FROM enrich.areas WHERE osm_type = 'relation'
"""


async def requeue(conn: AsyncConnection[TupleRow], features: bool) -> tuple[int, int]:
    """Returns the edges queued, and the ways and relations queued."""
    async with conn.transaction():
        edges = (await conn.execute(REQUEUE_EDGES)).rowcount
        if not features:
            return edges, 0
        params = {"match": [Jsonb(pattern) for layer in LAYERS for pattern in layer.match]}
        ways = (await conn.execute(REQUEUE_WAYS, params)).rowcount
        relations = (await conn.execute(REQUEUE_RELATIONS, params)).rowcount
    return edges, ways + relations


async def _run(features: bool) -> tuple[int, int]:
    # app.config reads the environment on import; here, so the tests can import this module.
    from app.config import ENRICHER_ROLE, ENRICHER_ROLE_PASSWORD

    conninfo = make_conninfo(user=ENRICHER_ROLE, password=ENRICHER_ROLE_PASSWORD)
    async with await AsyncConnection.connect(conninfo) as conn:
        return await requeue(conn, features)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.enrichment.requeue")
    parser.add_argument("--features", action="store_true", help="also rebuild every feature")
    args = parser.parse_args(argv)
    edges, features = asyncio.run(_run(args.features))
    print(f"Queued {edges} edges and {features} ways and relations.")


if __name__ == "__main__":
    main()
