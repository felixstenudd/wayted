import asyncio

import psycopg
import pytest
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from app.sources import queue
from app.sources.downloader import DownloadStatus, RectangleResult
from app.sources.registry import mark_fetched
from app.sources.tiles import Bounds, Tile, TileRect, bounds_for_tiles

pytestmark = pytest.mark.db

type Conn = AsyncConnection[TupleRow]
type Pool = AsyncConnectionPool[Conn]
# (layer, x, y, status, attempts)
type Row = tuple[str, int, int, str, int]

# The queue's mechanics run on two layers, so adding a layer leaves these tests alone.
LAYERS = ("roads", "parks")
RECT = TileRect(z=14, x_min=8800, y_min=4700, x_max=8801, y_max=4701)
TILES = RECT.tiles()
BOUNDS = bounds_for_tiles(TILES)
ONE = Tile(x=8800, y=4700, z=14)
ONE_RECT = TileRect.of_tile(ONE)


async def request(pool: Pool, bounds: Bounds = BOUNDS, refetch: bool = False) -> int:
    async with pool.connection() as conn:
        return sum((await queue.request_area(conn, bounds, refetch, LAYERS)).values())


async def rows(conn: Conn) -> list[Row]:
    cur = await conn.execute(
        "SELECT layer, x, y, status, attempts FROM raw.pending_tiles ORDER BY layer, x, y"
    )
    return await cur.fetchall()


async def queued_tiles(conn: Conn, layer: str) -> set[Tile]:
    cur = await conn.execute("SELECT x, y, z FROM raw.pending_tiles WHERE layer = %s", (layer,))
    return {Tile(x=x, y=y, z=z) for x, y, z in await cur.fetchall()}


async def test_request_queues_every_downloaded_layer(admin_conn: Conn, api_pool: Pool) -> None:
    async with api_pool.connection() as conn:
        queued = await queue.request_area(conn, BOUNDS)

    assert queued == {layer: len(TILES) for layer in queue.LAYER_CODES}
    assert {"roads", "parks", "nature"} <= set(queue.LAYER_CODES)
    for layer in queue.LAYER_CODES:
        assert await queued_tiles(admin_conn, layer) == TILES
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


async def test_request_counts_the_rows_queued_per_layer(
    api_pool: Pool, downloader_pool: Pool
) -> None:
    async with downloader_pool.connection() as conn:
        await mark_fetched(conn, "roads", {ONE})
        await mark_fetched(conn, "parks", TILES)

    async with api_pool.connection() as conn:
        queued = await queue.request_area(conn, BOUNDS, layers=LAYERS)

    # A layer with nothing to queue is still listed.
    assert queued == {"parks": 0, "roads": 3}


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


@pytest.mark.parametrize("refetch", [False, True])
async def test_running_tile_is_left_alone(admin_conn: Conn, api_pool: Pool, refetch: bool) -> None:
    await request(api_pool)
    await admin_conn.execute("UPDATE raw.pending_tiles SET status = 'running', attempts = 2")

    assert await request(api_pool, refetch=refetch) == 0

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


async def test_failed_tile_that_is_still_fetched_is_queued_again(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool
) -> None:
    # Fetched but never mapped: the mapper failed on every attempt.
    await request(api_pool, ONE.bounds)
    async with downloader_pool.connection() as conn:
        for layer in LAYERS:
            await mark_fetched(conn, layer, {ONE})
    await admin_conn.execute("UPDATE raw.pending_tiles SET status = 'failed', attempts = 10")

    assert await request(api_pool, ONE.bounds) == 2

    assert await rows(admin_conn) == [
        ("parks", ONE.x, ONE.y, "pending", 0),
        ("roads", ONE.x, ONE.y, "pending", 0),
    ]


async def test_request_does_not_block_the_worker_on_queued_tiles(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool
) -> None:
    await request(api_pool)

    async with api_pool.connection() as api_conn:
        # Asked again, and the API transaction is still open.
        assert await queue.request_area(api_conn, BOUNDS, layers=LAYERS) == {
            "parks": 0,
            "roads": 0,
        }
        async with downloader_pool.connection() as conn:
            claimed = await asyncio.wait_for(queue.claim(conn, LAYERS, 64), timeout=3)

    assert claimed == {"roads": TILES, "parks": TILES}


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


async def test_claim_marks_due_tiles_as_running(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool
) -> None:
    await request(api_pool)

    async with downloader_pool.connection() as conn:
        claimed = await queue.claim(conn, LAYERS, 64)

    assert claimed == {"roads": TILES, "parks": TILES}
    assert {status for _, _, _, status, _ in await rows(admin_conn)} == {"running"}


async def test_claim_takes_the_oldest_request_first_up_to_the_limit(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool
) -> None:
    later = Tile(x=8900, y=4700, z=14)
    await request(api_pool, later.bounds)
    await admin_conn.execute("UPDATE raw.pending_tiles SET requested_at = now()")
    await request(api_pool)
    await admin_conn.execute(
        "UPDATE raw.pending_tiles SET requested_at = now() - interval '1 hour' WHERE x <> %s",
        (later.x,),
    )

    async with downloader_pool.connection() as conn:
        first = await queue.claim(conn, LAYERS, 4)
        second = await queue.claim(conn, LAYERS, 4)

    # The limit counts tiles: both layers of a tile are claimed together.
    assert first == {"roads": TILES, "parks": TILES}
    assert second == {"roads": {later}, "parks": {later}}


async def test_claim_leaves_tiles_that_are_not_due(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool
) -> None:
    await request(api_pool)
    await admin_conn.execute(
        "UPDATE raw.pending_tiles SET next_attempt_at = now() + interval '1 minute'"
    )

    async with downloader_pool.connection() as conn:
        assert await queue.claim(conn, LAYERS, 64) == {}


async def test_claim_ignores_layers_it_was_not_asked_for(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool
) -> None:
    await request(api_pool)

    async with downloader_pool.connection() as conn:
        assert await queue.claim(conn, ("roads",), 64) == {"roads": TILES}

    assert {(layer, status) for layer, _, _, status, _ in await rows(admin_conn)} == {
        ("roads", "running"),
        ("parks", "pending"),
    }


async def claim_and_settle(
    pool: Pool, result: RectangleResult, mapper_error: str | None = None
) -> None:
    async with pool.connection() as conn:
        await queue.claim(conn, LAYERS, 64)
    async with pool.connection() as conn, conn.transaction():
        await queue.settle(conn, LAYERS, [result], mapper_error)


async def test_settle_removes_a_stored_rectangle(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool
) -> None:
    await request(api_pool)
    async with downloader_pool.connection() as conn:
        for layer in LAYERS:
            await mark_fetched(conn, layer, {ONE})

    await claim_and_settle(downloader_pool, RectangleResult(ONE_RECT, DownloadStatus.OK, None))

    assert await queued_tiles(admin_conn, "roads") == TILES - {ONE}
    assert await queued_tiles(admin_conn, "parks") == TILES - {ONE}


async def test_settle_keeps_a_tile_requested_after_its_rectangle_was_stored(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool
) -> None:
    # The rectangle is stored, and a refetch of one of its tiles arrives before the cycle settles.
    async with downloader_pool.connection() as conn:
        for layer in LAYERS:
            await mark_fetched(conn, layer, {ONE})
    assert await request(api_pool, ONE.bounds, refetch=True) == 2

    async with downloader_pool.connection() as conn, conn.transaction():
        await queue.settle(conn, LAYERS, [RectangleResult(ONE_RECT, DownloadStatus.OK, None)])

    assert await rows(admin_conn) == [
        ("parks", ONE.x, ONE.y, "pending", 0),
        ("roads", ONE.x, ONE.y, "pending", 0),
    ]


@pytest.mark.parametrize("stored_first", [True, False])
async def test_settle_with_overlapping_rectangles(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool, stored_first: bool
) -> None:
    # RECT was stored, and a rectangle sharing its east column timed out.
    east = TileRect(z=14, x_min=8801, y_min=4700, x_max=8802, y_max=4701)
    await request(api_pool, bounds_for_tiles(TILES | east.tiles()))
    async with downloader_pool.connection() as conn:
        await queue.claim(conn, LAYERS, 64)
        for layer in LAYERS:
            await mark_fetched(conn, layer, TILES)
    results = [
        RectangleResult(RECT, DownloadStatus.OK, None),
        RectangleResult(east, DownloadStatus.TIMEOUT, "slow"),
    ]

    async with downloader_pool.connection() as conn, conn.transaction():
        await queue.settle(conn, LAYERS, results if stored_first else results[::-1])

    assert await queued_tiles(admin_conn, "roads") == east.tiles() - TILES
    assert {(status, attempts) for _, _, _, status, attempts in await rows(admin_conn)} == {
        ("pending", 1)
    }


@pytest.mark.parametrize(
    "status",
    [
        DownloadStatus.RATE_LIMITED,
        DownloadStatus.TIMEOUT,
        DownloadStatus.SOURCE_ERROR,
        DownloadStatus.STORAGE_ERROR,
    ],
)
async def test_settle_retries_a_failure_that_can_pass(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool, status: DownloadStatus
) -> None:
    await request(api_pool, ONE.bounds)

    await claim_and_settle(downloader_pool, RectangleResult(ONE_RECT, status, "try later"))

    cur = await admin_conn.execute(
        """
        SELECT status, attempts, last_status, last_message,
            next_attempt_at - now() BETWEEN interval '50 seconds' AND interval '1 minute'
        FROM raw.pending_tiles
        """
    )
    assert set(await cur.fetchall()) == {("pending", 1, status.value, "try later", True)}


async def test_settle_waits_longer_after_each_attempt(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool
) -> None:
    await request(api_pool, ONE.bounds)
    await admin_conn.execute("UPDATE raw.pending_tiles SET attempts = 2")

    await claim_and_settle(
        downloader_pool, RectangleResult(ONE_RECT, DownloadStatus.TIMEOUT, "slow")
    )

    cur = await admin_conn.execute(
        """
        SELECT status, attempts,
            next_attempt_at - now() BETWEEN interval '170 seconds' AND interval '3 minutes'
        FROM raw.pending_tiles
        """
    )
    assert set(await cur.fetchall()) == {("pending", 3, True)}


async def test_settle_retries_the_ninth_attempt(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool
) -> None:
    await request(api_pool, ONE.bounds)
    await admin_conn.execute("UPDATE raw.pending_tiles SET attempts = 8")

    await claim_and_settle(
        downloader_pool, RectangleResult(ONE_RECT, DownloadStatus.TIMEOUT, "slow")
    )

    assert await rows(admin_conn) == [
        ("parks", ONE.x, ONE.y, "pending", 9),
        ("roads", ONE.x, ONE.y, "pending", 9),
    ]


async def test_settle_fails_the_tenth_attempt(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool
) -> None:
    await request(api_pool, ONE.bounds)
    await admin_conn.execute("UPDATE raw.pending_tiles SET attempts = 9")

    await claim_and_settle(
        downloader_pool, RectangleResult(ONE_RECT, DownloadStatus.TIMEOUT, "slow")
    )

    assert await rows(admin_conn) == [
        ("parks", ONE.x, ONE.y, "failed", 10),
        ("roads", ONE.x, ONE.y, "failed", 10),
    ]


async def test_settle_fails_a_rejected_request_at_once(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool
) -> None:
    await request(api_pool, ONE.bounds)

    await claim_and_settle(
        downloader_pool, RectangleResult(ONE_RECT, DownloadStatus.INVALID_RESPONSE, "bad query")
    )

    cur = await admin_conn.execute(
        "SELECT status, attempts, last_status, last_message FROM raw.pending_tiles"
    )
    assert set(await cur.fetchall()) == {("failed", 1, "invalid_response", "bad query")}


async def test_settle_retries_a_stored_rectangle_when_the_mapper_failed(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool
) -> None:
    await request(api_pool, ONE.bounds)

    await claim_and_settle(
        downloader_pool, RectangleResult(ONE_RECT, DownloadStatus.OK, None), "division by zero"
    )

    cur = await admin_conn.execute(
        "SELECT status, attempts, last_status, last_message FROM raw.pending_tiles"
    )
    assert set(await cur.fetchall()) == {("pending", 1, "mapper_error", "division by zero")}


async def test_settle_leaves_a_failed_rectangles_unclaimed_tiles(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool
) -> None:
    await request(api_pool)
    async with downloader_pool.connection() as conn:
        await queue.claim(conn, LAYERS, 1)

    async with downloader_pool.connection() as conn, conn.transaction():
        await queue.settle(conn, LAYERS, [RectangleResult(RECT, DownloadStatus.TIMEOUT, "slow")])

    assert {(status, attempts) for _, _, _, status, attempts in await rows(admin_conn)} == {
        ("pending", 0),
        ("pending", 1),
    }
    cur = await admin_conn.execute("SELECT count(*) FROM raw.pending_tiles WHERE attempts = 1")
    assert await cur.fetchone() == (2,)


async def test_reset_running_returns_rows_to_the_queue(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool
) -> None:
    await request(api_pool)
    async with downloader_pool.connection() as conn:
        await queue.claim(conn, LAYERS, 1)

    async with downloader_pool.connection() as conn:
        assert await queue.reset_running(conn) == 2

    assert {status for _, _, _, status, _ in await rows(admin_conn)} == {"pending"}


async def test_seconds_until_due(admin_conn: Conn, api_pool: Pool, downloader_pool: Pool) -> None:
    async with downloader_pool.connection() as conn:
        assert await queue.seconds_until_due(conn, LAYERS) is None

    await request(api_pool)
    async with downloader_pool.connection() as conn:
        assert await queue.seconds_until_due(conn, LAYERS) == 0.0

    await admin_conn.execute(
        "UPDATE raw.pending_tiles SET next_attempt_at = now() + interval '1 minute'"
    )
    await admin_conn.execute(
        "UPDATE raw.pending_tiles SET status = 'failed', next_attempt_at = now() WHERE x = %s",
        (ONE.x,),
    )
    async with downloader_pool.connection() as conn:
        seconds = await queue.seconds_until_due(conn, LAYERS)
    assert seconds is not None and 50 < seconds <= 60


async def test_seconds_until_due_ignores_layers_the_worker_does_not_fetch(
    admin_conn: Conn, downloader_pool: Pool
) -> None:
    # Claim would never take this row, so waiting on it would spin.
    await admin_conn.execute(
        "INSERT INTO raw.pending_tiles (layer, z, x, y) VALUES ('green_areas', 14, 8800, 4700)"
    )

    async with downloader_pool.connection() as conn:
        assert await queue.seconds_until_due(conn, LAYERS) is None


async def test_queued_tiles_carry_their_state(admin_conn: Conn, api_pool: Pool) -> None:
    west, east = ONE, Tile(x=ONE.x + 1, y=ONE.y, z=14)
    await request(api_pool, bounds_for_tiles({west, east}))
    await admin_conn.execute(
        """
        UPDATE raw.pending_tiles
        SET status = 'failed', attempts = 10, last_status = 'timeout', last_message = 'too slow',
            requested_at = requested_at - interval '1 hour'
        WHERE layer = 'roads' AND x = %s
        """,
        (east.x,),
    )

    async with api_pool.connection() as conn:
        listed = await queue.queued_tiles(conn)

    assert [(q.layer, q.tile) for q in listed] == [
        ("roads", east),
        ("parks", west),
        ("parks", east),
        ("roads", west),
    ]
    failed, waiting = listed[0], listed[1]
    assert (failed.status, failed.attempts, failed.last_status, failed.last_message) == (
        "failed",
        10,
        "timeout",
        "too slow",
    )
    assert (waiting.status, waiting.attempts, waiting.last_status, waiting.last_message) == (
        "pending",
        0,
        None,
        None,
    )
    assert failed.requested_at < waiting.requested_at <= waiting.next_attempt_at


async def test_queued_tiles_of_an_empty_queue(admin_conn: Conn, api_pool: Pool) -> None:
    async with api_pool.connection() as conn:
        assert await queue.queued_tiles(conn) == []
