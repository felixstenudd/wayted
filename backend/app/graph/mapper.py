"""Builds the routable graph from the ways and nodes queued by the triggers on raw."""

from dataclasses import dataclass

from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from . import queries


@dataclass(frozen=True, slots=True)
class BatchResult:
    ways_claimed: int
    nodes_claimed: int
    ways_skipped: int  # a node missing from raw, or fewer than two nodes
    edges_inserted: int
    edges_updated: int
    edges_deleted: int


@dataclass(frozen=True, slots=True)
class MapResult:
    batches: tuple[BatchResult, ...]


async def map_pending(
    pool: AsyncConnectionPool[AsyncConnection[TupleRow]], batch_size: int = 5000
) -> MapResult:
    """Map queued ways and nodes, one transaction per batch, until both queues are empty."""
    batches: list[BatchResult] = []
    while True:
        async with pool.connection() as conn:
            batch = await _map_batch(conn, batch_size)
        if batch is None:
            return MapResult(tuple(batches))
        batches.append(batch)


async def _map_batch(conn: AsyncConnection[TupleRow], batch_size: int) -> BatchResult | None:
    async with conn.transaction():
        # Every statement of the batch sees the same raw, even while the downloader writes.
        await conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        # Work tables start without statistics, so the planner overestimates and compiles
        # small batches with JIT, which costs more than the batch itself.
        await conn.execute("SET LOCAL jit = off")
        await conn.execute(queries.CREATE_WORK_TABLES)
        params = {"batch_size": batch_size}
        ways_claimed = (await conn.execute(queries.CLAIM_WAYS, params)).rowcount
        nodes_claimed = (await conn.execute(queries.CLAIM_NODES, params)).rowcount
        if ways_claimed == 0 and nodes_claimed == 0:
            return None
        await conn.execute("ANALYZE claimed_ways, moved_nodes")
        await conn.execute(queries.FIND_AFFECTED_WAYS)
        await conn.execute("ANALYZE affected_ways")
        await conn.execute(queries.CLASSIFY_WAYS)
        await conn.execute("ANALYZE routable_ways")
        await conn.execute(queries.BUILD_SEGMENTS)
        await conn.execute("ANALYZE segments")
        cur = await conn.execute(queries.COUNT_SKIPPED_WAYS)
        row = await cur.fetchone()
        assert row is not None
        ways_skipped: int = row[0]
        await conn.execute(queries.CLASSIFY_CHANGES)
        await conn.execute(queries.FIND_RETAGGED_WAYS)
        await conn.execute(queries.UPSERT_WAYS)
        await conn.execute(queries.UPSERT_VERTICES)
        edges_deleted = (await conn.execute(queries.DELETE_STALE_EDGES)).rowcount
        await conn.execute(queries.REQUEUE_DROPPED_ENDS)
        edges_updated = (await conn.execute(queries.UPDATE_EDGES)).rowcount
        await conn.execute(queries.QUEUE_CHANGED_EDGES)
        edges_inserted = (await conn.execute(queries.INSERT_EDGES)).rowcount
        await conn.execute(queries.DELETE_UNROUTABLE_WAYS)
        await conn.execute(queries.DELETE_UNUSED_VERTICES)
    return BatchResult(
        ways_claimed=ways_claimed,
        nodes_claimed=nodes_claimed,
        ways_skipped=ways_skipped,
        edges_inserted=edges_inserted,
        edges_updated=edges_updated,
        edges_deleted=edges_deleted,
    )
