import asyncio

import psycopg
import pytest
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from app.db import PIPELINE_LOCK, pipeline_lock
from app.enrichment import enrich_pending
from app.graph import map_pending

from .raw_data import add_line

pytestmark = pytest.mark.db

type Conn = AsyncConnection[TupleRow]
type Pool = AsyncConnectionPool[Conn]


async def lock_is_free(conn: Conn) -> bool:
    cur = await conn.execute(
        """
        SELECT NOT EXISTS (
            SELECT 1 FROM pg_locks WHERE locktype = 'advisory' AND objid = %s AND granted
        )
        """,
        (PIPELINE_LOCK,),
    )
    row = await cur.fetchone()
    assert row is not None
    return bool(row[0])


async def test_mapper_waits_while_the_lock_is_held(admin_conn: Conn, mapper_pool: Pool) -> None:
    await add_line(admin_conn, 1, [(1, 0, 0), (2, 1, 0)], {"highway": "path"})

    async with mapper_pool.connection() as holder, pipeline_lock(holder):
        mapping = asyncio.create_task(map_pending(mapper_pool.connection))
        await asyncio.sleep(0.3)
        assert not mapping.done()
    result = await asyncio.wait_for(mapping, timeout=5)

    assert sum(b.edges_inserted for b in result.batches) == 1


async def test_enricher_waits_while_the_lock_is_held(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_line(admin_conn, 1, [(1, 0, 0), (2, 1, 0)], {"highway": "path"})
    await map_pending(mapper_pool.connection)

    async with mapper_pool.connection() as holder, pipeline_lock(holder):
        enriching = asyncio.create_task(enrich_pending(enricher_pool.connection))
        await asyncio.sleep(0.3)
        assert not enriching.done()
    result = await asyncio.wait_for(enriching, timeout=5)

    assert sum(b.edges_scored for b in result.batches) == 1


async def test_lock_is_released_when_the_batch_fails(admin_conn: Conn, mapper_pool: Pool) -> None:
    async with mapper_pool.connection() as conn:
        with pytest.raises(psycopg.errors.DivisionByZero):
            async with pipeline_lock(conn), conn.transaction():
                await conn.execute("SELECT 1 / 0")

    assert await lock_is_free(admin_conn)


async def test_lock_does_not_outlive_the_block(admin_conn: Conn, mapper_pool: Pool) -> None:
    async with mapper_pool.connection() as conn:
        async with pipeline_lock(conn):
            assert not await lock_is_free(admin_conn)
        assert await lock_is_free(admin_conn)
