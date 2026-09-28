import pytest
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from app.sources.registry import mark_fetched
from app.sources.tiles import Tile

pytestmark = pytest.mark.db

TILES = {Tile(x=8800, y=4700, z=14), Tile(x=8801, y=4700, z=14)}


async def test_mark_fetched_records_tiles_with_the_layer_ttl(
    admin_conn: AsyncConnection[TupleRow],
    downloader_pool: AsyncConnectionPool[AsyncConnection[TupleRow]],
) -> None:
    async with downloader_pool.connection() as conn:
        await mark_fetched(conn, "roads", TILES)

    cur = await admin_conn.execute(
        """
        SELECT t.layer, t.z, t.x, t.y, t.expires_at = t.fetched_at + l.ttl
        FROM raw.fetched_tiles t JOIN ref.source_layers l ON l.code = t.layer
        ORDER BY t.x
        """
    )
    assert await cur.fetchall() == [
        ("roads", 14, 8800, 4700, True),
        ("roads", 14, 8801, 4700, True),
    ]


async def test_mark_fetched_again_updates_instead_of_duplicating(
    admin_conn: AsyncConnection[TupleRow],
    downloader_pool: AsyncConnectionPool[AsyncConnection[TupleRow]],
) -> None:
    async with downloader_pool.connection() as conn:
        await mark_fetched(conn, "roads", TILES)
    await admin_conn.execute(
        "UPDATE raw.fetched_tiles SET fetched_at = fetched_at - interval '1 day'"
    )

    async with downloader_pool.connection() as conn:
        await mark_fetched(conn, "roads", TILES)

    cur = await admin_conn.execute(
        "SELECT count(*), bool_and(fetched_at > now() - interval '1 hour') FROM raw.fetched_tiles"
    )
    assert await cur.fetchone() == (2, True)
