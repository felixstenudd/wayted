import psycopg
import pytest
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from app.sources import queue
from app.sources.registry import mark_fetched
from app.sources.tiles import Bounds, Tile, TileRect, bounds_for_tiles

pytestmark = pytest.mark.db

type Conn = AsyncConnection[TupleRow]
type Pool = AsyncConnectionPool[Conn]
# (layer, x, y, status, attempts)
type Row = tuple[str, int, int, str, int]

RECT = TileRect(z=14, x_min=8800, y_min=4700, x_max=8801, y_max=4701)
TILES = RECT.tiles()
BOUNDS = bounds_for_tiles(TILES)
ONE = Tile(x=8800, y=4700, z=14)


async def request(pool: Pool, bounds: Bounds = BOUNDS, refetch: bool = False) -> int:
    async with pool.connection() as conn:
        return await queue.request_area(conn, bounds, refetch)


async def rows(conn: Conn) -> list[Row]:
    cur = await conn.execute(
        "SELECT layer, x, y, status, attempts FROM raw.pending_tiles ORDER BY layer, x, y"
    )
    return await cur.fetchall()


async def queued_tiles(conn: Conn, layer: str) -> set[Tile]:
    cur = await conn.execute("SELECT x, y, z FROM raw.pending_tiles WHERE layer = %s", (layer,))
    return {Tile(x=x, y=y, z=z) for x, y, z in await cur.fetchall()}


async def test_request_queues_every_fetched_layer(admin_conn: Conn, api_pool: Pool) -> None:
    assert await request(api_pool) == 8

    assert await queued_tiles(admin_conn, "roads") == TILES
    assert await queued_tiles(admin_conn, "parks") == TILES
    # green_areas is in ref.source_layers, but nothing downloads it.
    assert await queued_tiles(admin_conn, "green_areas") == set()
    assert {(status, attempts) for _, _, _, status, attempts in await rows(admin_conn)} == {
        ("pending", 0)
    }


async def test_point_bounds_queue_the_tile_around_the_point(
    admin_conn: Conn, api_pool: Pool
) -> None:
    point = Bounds(west=18.07, south=59.33, east=18.07, north=59.33)

    assert await request(api_pool, point) == 2

    tile = Tile.from_lat_lon(59.33, 18.07, 14)
    assert await queued_tiles(admin_conn, "roads") == {tile}
    assert await queued_tiles(admin_conn, "parks") == {tile}


async def test_fetched_tiles_are_skipped(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool
) -> None:
    async with downloader_pool.connection() as conn:
        await mark_fetched(conn, "roads", {ONE})

    assert await request(api_pool) == 7

    assert await queued_tiles(admin_conn, "roads") == TILES - {ONE}
    assert await queued_tiles(admin_conn, "parks") == TILES


async def test_expired_tiles_are_queued(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool
) -> None:
    async with downloader_pool.connection() as conn:
        await mark_fetched(conn, "roads", TILES)
    await admin_conn.execute(
        """
        UPDATE raw.fetched_tiles
        SET fetched_at = now() - interval '2 months', expires_at = now() - interval '1 month'
        WHERE (x, y) = (%s, %s)
        """,
        (ONE.x, ONE.y),
    )

    assert await request(api_pool) == 5

    assert await queued_tiles(admin_conn, "roads") == {ONE}


async def test_refetch_queues_fetched_tiles(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool
) -> None:
    async with downloader_pool.connection() as conn:
        await mark_fetched(conn, "roads", TILES)

    assert await request(api_pool, refetch=True) == 8

    assert await queued_tiles(admin_conn, "roads") == TILES


async def test_second_request_adds_nothing(admin_conn: Conn, api_pool: Pool) -> None:
    await request(api_pool)
    before = await rows(admin_conn)

    assert await request(api_pool) == 0

    assert await rows(admin_conn) == before


async def test_running_tile_is_left_alone(admin_conn: Conn, api_pool: Pool) -> None:
    await request(api_pool)
    await admin_conn.execute("UPDATE raw.pending_tiles SET status = 'running', attempts = 2")

    assert await request(api_pool) == 0

    assert {(status, attempts) for _, _, _, status, attempts in await rows(admin_conn)} == {
        ("running", 2)
    }


async def test_failed_tile_is_queued_again(admin_conn: Conn, api_pool: Pool) -> None:
    await request(api_pool)
    await admin_conn.execute(
        """
        UPDATE raw.pending_tiles
        SET status = 'failed', attempts = 5, last_status = 'timeout', last_message = 'slow',
            next_attempt_at = now() + interval '1 hour'
        WHERE (layer, x, y) = ('roads', %s, %s)
        """,
        (ONE.x, ONE.y),
    )

    assert await request(api_pool) == 1

    cur = await admin_conn.execute(
        """
        SELECT status, attempts, last_status, last_message, next_attempt_at <= now()
        FROM raw.pending_tiles WHERE (layer, x, y) = ('roads', %s, %s)
        """,
        (ONE.x, ONE.y),
    )
    assert await cur.fetchall() == [("pending", 0, None, None, True)]


async def test_api_role_reaches_the_queue_but_not_raw_data(api_pool: Pool) -> None:
    async with api_pool.connection() as conn:
        await conn.execute("SELECT count(*) FROM raw.fetched_tiles")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            await conn.execute("SELECT count(*) FROM raw.osm_ways")


async def test_only_a_request_notifies_the_worker(
    admin_conn: Conn, api_pool: Pool, listener: Conn
) -> None:
    await listener.execute("LISTEN pending_tiles")

    await request(api_pool)
    woken = [n.channel async for n in listener.notifies(timeout=5, stop_after=1)]
    # What the worker does to the rows must not wake it again.
    await admin_conn.execute("UPDATE raw.pending_tiles SET status = 'running'")
    await admin_conn.execute("DELETE FROM raw.pending_tiles WHERE x = %s", (ONE.x,))
    woken_again = [n.channel async for n in listener.notifies(timeout=0.3)]

    assert woken == ["pending_tiles"]
    assert woken_again == []
