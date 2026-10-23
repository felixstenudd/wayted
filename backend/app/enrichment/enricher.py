"""
Builds features from the elements queued by the triggers on raw, scores edges near them, and
counts users' segment reviews of queued edges.
"""

from dataclasses import dataclass
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import TupleRow, dict_row

from app.db import Connect, pipeline_lock

from . import queries
from .attributes import HeightChange
from .definitions import ATTRIBUTES, LAYERS

HEIGHTS_REACH_M = max((a.reach_m for a in ATTRIBUTES if isinstance(a, HeightChange)), default=0)


@dataclass(frozen=True, slots=True)
class BatchResult:
    ways_claimed: int
    relations_claimed: int
    nodes_claimed: int
    elevation_tiles_claimed: int
    features_built: int
    features_deleted: int
    features_skipped: int  # a missing way or node, an open area, a line under two nodes, or empty
    edges_queued: int  # by changed features and heights
    edges_scored: int


@dataclass(frozen=True, slots=True)
class EnrichResult:
    batches: tuple[BatchResult, ...]


async def enrich_pending(connect: Connect, batch_size: int = 5000) -> EnrichResult:
    """Rebuild queued features and score queued edges, one transaction per batch, until done."""
    async with connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(queries.LAST_QUEUED_FEATURES)
        backlog = await cur.fetchone()
    assert backlog is not None
    batches: list[BatchResult] = []
    while True:
        async with connect() as conn, pipeline_lock(conn):
            batch = await _enrich_batch(conn, batch_size, backlog)
        if batch is None:
            return EnrichResult(tuple(batches))
        batches.append(batch)


async def _enrich_batch(
    conn: AsyncConnection[TupleRow], batch_size: int, backlog: dict[str, Any]
) -> BatchResult | None:
    async with conn.transaction():
        await conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        # As in the mapper: unanalyzed work tables make the planner compile small batches.
        await conn.execute("SET LOCAL jit = off")
        await conn.execute(queries.CREATE_WORK_TABLES)
        params = {"batch_size": batch_size}
        ways_claimed = (await conn.execute(queries.CLAIM_WAYS, params)).rowcount
        relations_claimed = (await conn.execute(queries.CLAIM_RELATIONS, params)).rowcount
        nodes_claimed = (await conn.execute(queries.CLAIM_NODES, params)).rowcount
        elevation_claimed = (await conn.execute(queries.CLAIM_ELEVATION, params)).rowcount
        if (ways_claimed, relations_claimed, nodes_claimed, elevation_claimed) == (0, 0, 0, 0):
            cur = await conn.execute(queries.HAS_PENDING_EDGES)
            row = await cur.fetchone()
            if row is None or not row[0]:
                return None
        await conn.execute("ANALYZE claimed_ways, claimed_relations, moved_nodes")
        await conn.execute(queries.FIND_CANDIDATES)
        await conn.execute("ANALYZE feature_candidates")
        await conn.execute(queries.FORGET_FEATURE_WAYS)
        built = deleted = skipped = 0
        for layer in LAYERS:
            result = await layer.rebuild(conn)
            built += result.built
            deleted += result.deleted
            skipped += result.skipped
        edges_queued = 0
        for layer in LAYERS:
            reaches = [a.reach_m for a in ATTRIBUTES if layer in a.layers]
            if reaches:
                queue_params = {"layer": layer.code, "reach_m": max(reaches)}
                edges_queued += (
                    await conn.execute(queries.QUEUE_NEAR_CHANGED, queue_params)
                ).rowcount
        edges_queued += (
            await conn.execute(queries.QUEUE_ON_CHANGED_ELEVATION, {"reach_m": HEIGHTS_REACH_M})
        ).rowcount
        # Scores once every feature queued before the run is built, as a later one would queue
        # the same edges again; then sees the edges queued just above.
        cur = await conn.execute(queries.HAS_EARLIER_FEATURES, backlog)
        row = await cur.fetchone()
        edges_scored = 0
        if row is not None and not row[0]:
            edges_scored = (await conn.execute(queries.CLAIM_EDGES, params)).rowcount
            await conn.execute("ANALYZE claimed_edges")
            for attribute in ATTRIBUTES:
                await attribute.score(conn)
            await conn.execute(queries.COUNT_FEEDBACK)
    return BatchResult(
        ways_claimed=ways_claimed,
        relations_claimed=relations_claimed,
        nodes_claimed=nodes_claimed,
        elevation_tiles_claimed=elevation_claimed,
        features_built=built,
        features_deleted=deleted,
        features_skipped=skipped,
        edges_queued=edges_queued,
        edges_scored=edges_scored,
    )
