import asyncio

import pytest
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from app.sources.registry import fetched_tiles, mark_fetched
from app.sources.tiles import Tile, TileRect

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


async def test_concurrent_marks_in_opposite_orders_do_not_deadlock(
    admin_conn: AsyncConnection[TupleRow],
    downloader_pool: AsyncConnectionPool[AsyncConnection[TupleRow]],
) -> None:
    tiles = sorted(
        TileRect(z=14, x_min=8000, y_min=4000, x_max=8063, y_max=4063).tiles(),
        key=lambda t: (t.x, t.y),
    )

    async def mark(order: list[Tile]) -> None:
        async with downloader_pool.connection() as conn:
            await mark_fetched(conn, "roads", order)

    for _ in range(3):
        await asyncio.gather(mark(tiles), mark(tiles[::-1]))


async def test_fetched_tiles_come_oldest_first(
    admin_conn: AsyncConnection[TupleRow],
    downloader_pool: AsyncConnectionPool[AsyncConnection[TupleRow]],
    api_pool: AsyncConnectionPool[AsyncConnection[TupleRow]],
) -> None:
    west, east = sorted(TILES, key=lambda t: t.x)
    async with downloader_pool.connection() as conn:
        await mark_fetched(conn, "roads", {west, east})
        await mark_fetched(conn, "parks", {west})
    await admin_conn.execute(
        "UPDATE raw.fetched_tiles SET fetched_at = fetched_at - interval '1 day' WHERE x = %s",
        (east.x,),
    )

    async with api_pool.connection() as conn:
        fetched = await fetched_tiles(conn)

    assert [(f.layer, f.tile) for f in fetched] == [
        ("roads", east),
        ("parks", west),
        ("roads", west),
    ]
    assert fetched[0].fetched_at < fetched[1].fetched_at
    assert all(f.expires_at > f.fetched_at for f in fetched)


async def test_fetched_tiles_include_expired_ones(
    admin_conn: AsyncConnection[TupleRow],
    downloader_pool: AsyncConnectionPool[AsyncConnection[TupleRow]],
    api_pool: AsyncConnectionPool[AsyncConnection[TupleRow]],
) -> None:
    async with downloader_pool.connection() as conn:
        await mark_fetched(conn, "roads", TILES)
    await admin_conn.execute(
        """
        UPDATE raw.fetched_tiles
        SET fetched_at = now() - interval '2 months', expires_at = now() - interval '1 month'
        """
    )

    async with api_pool.connection() as conn:
        assert {f.tile for f in await fetched_tiles(conn)} == TILES


async def test_fetched_tiles_of_an_empty_registry(
    admin_conn: AsyncConnection[TupleRow],
    api_pool: AsyncConnectionPool[AsyncConnection[TupleRow]],
) -> None:
    async with api_pool.connection() as conn:
        assert await fetched_tiles(conn) == []
