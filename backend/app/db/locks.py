from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from psycopg import AsyncConnection
from psycopg.rows import TupleRow

PIPELINE_LOCK = 1


@asynccontextmanager
async def pipeline_lock(conn: AsyncConnection[TupleRow]) -> AsyncIterator[None]:
    """
    Hold the lock the mapper and the enricher take around each batch, so their batches never
    overlap. Taken outside any transaction: a REPEATABLE READ snapshot taken before the lock
    would predate the other batch's commit.
    """
    await conn.execute("SELECT pg_advisory_lock(%s)", (PIPELINE_LOCK,))
    await conn.commit()
    try:
        yield
    finally:
        await conn.execute("SELECT pg_advisory_unlock(%s)", (PIPELINE_LOCK,))
        await conn.commit()
