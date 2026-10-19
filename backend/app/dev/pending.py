"""How much work the mapper and the enricher have left, from their queues."""

from dataclasses import dataclass

from psycopg import AsyncConnection
from psycopg.rows import TupleRow

# The queues are append-only, so one id can wait in several rows.
PENDING = """
    SELECT (SELECT count(DISTINCT way_id) FROM graph.pending_ways),
           (SELECT count(DISTINCT node_id) FROM graph.pending_nodes),
           (SELECT count(DISTINCT way_id) FROM enrich.pending_ways),
           (SELECT count(DISTINCT relation_id) FROM enrich.pending_relations),
           (SELECT count(DISTINCT node_id) FROM enrich.pending_nodes),
           (SELECT count(DISTINCT edge_id) FROM graph.pending_edges)
"""


@dataclass(frozen=True, slots=True)
class MapperPending:
    ways: int
    nodes: int


@dataclass(frozen=True, slots=True)
class EnricherPending:
    ways: int
    relations: int
    nodes: int
    edges: int


@dataclass(frozen=True, slots=True)
class Pending:
    mapper: MapperPending
    enricher: EnricherPending


async def pending_counts(conn: AsyncConnection[TupleRow]) -> Pending:
    cur = await conn.execute(PENDING)
    row = await cur.fetchone()
    assert row is not None
    return Pending(MapperPending(*row[:2]), EnricherPending(*row[2:]))
