import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import TypeAlias

from psycopg import AsyncConnection
from psycopg.conninfo import make_conninfo
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

Pool: TypeAlias = AsyncConnectionPool[AsyncConnection[TupleRow]]  # noqa: UP040

# Lends out a connection for one `async with` block. For code that opens several connections
# over time, so it can take e.g. `lambda: db.connection(role)` or a test pool's `.connection`.
Connect: TypeAlias = Callable[[], AbstractAsyncContextManager[AsyncConnection[TupleRow]]]  # noqa: UP040

_pools: dict[str, Pool] = {}


async def open_pool(role: str, password: str) -> None:
    if role in _pools:
        raise RuntimeError(f"Pool for {role} is already open")
    pool: Pool = AsyncConnectionPool(make_conninfo(user=role, password=password), open=False)
    await pool.open(wait=True, timeout=10)
    _pools[role] = pool


async def close_pools() -> None:
    pools = list(_pools.values())
    _pools.clear()
    await asyncio.gather(*(pool.close() for pool in pools), return_exceptions=True)


def connection(role: str) -> AbstractAsyncContextManager[AsyncConnection[TupleRow]]:
    pool = _pools.get(role)
    if pool is None:
        raise RuntimeError(f"No pool open for {role}")
    return pool.connection()
