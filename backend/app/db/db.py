import asyncio
import os

from psycopg.conninfo import make_conninfo
from psycopg_pool import AsyncConnectionPool

_pools: dict[str, AsyncConnectionPool] = {}


async def open_pool(role: str, password: str) -> None:
    if role in _pools:
        raise RuntimeError(f"Pool for {role} is already open")
    pool = AsyncConnectionPool(make_conninfo(user=role, password=password), open=False)
    await pool.open(wait=True, timeout=10)
    _pools[role] = pool


async def close_pools() -> None:
    pools = list(_pools.values())
    _pools.clear()
    await asyncio.gather(*(pool.close() for pool in pools), return_exceptions=True)


def connection(role: str):
    pool = _pools.get(role)
    if pool is None:
        raise RuntimeError(f"No pool open for {role}")
    return pool.connection()


api_pool = AsyncConnectionPool(
    make_conninfo(user="wayted_api", password=os.environ["WAYTED_API_PASSWORD"]),
    open=False,
)
