import asyncio
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress

import pytest
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from app import worker
from app.graph import queries
from app.sources import queue
from app.sources.downloader import DownloadError, DownloadStatus
from app.sources.tiles import Bounds, Tile, TileRect, bounds_for_tiles

from .graph.raw_data import add_line

pytestmark = pytest.mark.db

type Conn = AsyncConnection[TupleRow]
type Pool = AsyncConnectionPool[Conn]

# Two 2x2 clusters with a 2-column gap between them: merging them costs 4 extra tiles.
WEST = {Tile(x=x, y=y, z=14) for x in (8800, 8801) for y in (4700, 4701)}
GAP = {Tile(x=x, y=y, z=14) for x in (8802, 8803) for y in (4700, 4701)}
EAST = {Tile(x=x, y=y, z=14) for x in (8804, 8805) for y in (4700, 4701)}


class RoadDownloader:
    """
    Stores one short residential road per rectangle, the same road when a rectangle is fetched
    again. A fetch can be told to fail by its call number.
    """

    layers: tuple[str, ...] = ("roads", "parks")
    max_tiles = 64

    def __init__(
        self, max_extra_tiles: int = 0, fetch_errors: dict[int, Exception] | None = None
    ) -> None:
        self.max_extra_tiles = max_extra_tiles
        self.fetch_errors = fetch_errors or {}
        self.calls = 0
        self.way_ids: dict[Bounds, int] = {}

    async def fetch(self, bounds: Bounds) -> int:
        self.calls += 1
        if self.calls in self.fetch_errors:
            raise self.fetch_errors[self.calls]
        return self.way_ids.setdefault(bounds, len(self.way_ids) + 1)

    async def store(self, conn: Conn, payload: int) -> None:
        first_node = payload * 2
        await add_line(
            conn,
            payload,
            [(first_node, payload, 0), (first_node + 1, payload, 1)],
            {"highway": "residential"},
        )


class OpenWaterDownloader(RoadDownloader):
    """An area with no features: Overpass returns no elements."""

    async def store(self, conn: Conn, payload: int) -> None:
        pass


async def request(pool: Pool, tiles: set[Tile]) -> None:
    async with pool.connection() as conn:
        await queue.request_area(conn, bounds_for_tiles(tiles), layers=RoadDownloader.layers)


async def run(
    downloader: RoadDownloader, downloader_pool: Pool, mapper_pool: Pool
) -> worker.CycleResult | None:
    return await worker.run_once([downloader], downloader_pool.connection, mapper_pool.connection)


async def queued(conn: Conn) -> dict[Tile, set[tuple[str, int, str | None]]]:
    """Queue rows as tile -> {(status, attempts, last_status)} over its layers."""
    cur = await conn.execute("SELECT x, y, z, status, attempts, last_status FROM raw.pending_tiles")
    tiles: dict[Tile, set[tuple[str, int, str | None]]] = {}
    for x, y, z, status, attempts, last_status in await cur.fetchall():
        tiles.setdefault(Tile(x=x, y=y, z=z), set()).add((status, attempts, last_status))
    return tiles


async def fetched(conn: Conn, layer: str) -> set[Tile]:
    cur = await conn.execute("SELECT x, y, z FROM raw.fetched_tiles WHERE layer = %s", (layer,))
    return {Tile(x=x, y=y, z=z) for x, y, z in await cur.fetchall()}


async def edge_count(conn: Conn) -> int:
    cur = await conn.execute("SELECT count(*) FROM graph.edges")
    row = await cur.fetchone()
    assert row is not None
    count: int = row[0]
    return count


async def test_cycle_fetches_and_maps_the_requested_tiles(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool, mapper_pool: Pool
) -> None:
    await request(api_pool, WEST)

    result = await run(RoadDownloader(), downloader_pool, mapper_pool)

    assert result is not None
    assert result.tiles_claimed == 4
    assert [(r.rect, r.status) for r in result.rectangles] == [
        (TileRect(z=14, x_min=8800, y_min=4700, x_max=8801, y_max=4701), DownloadStatus.OK)
    ]
    assert result.mapped is not None
    assert [b.edges_inserted for b in result.mapped.batches] == [1]
    assert await fetched(admin_conn, "roads") == WEST
    assert await fetched(admin_conn, "parks") == WEST
    assert await edge_count(admin_conn) == 1
    assert await queued(admin_conn) == {}


async def test_nothing_due_fetches_nothing(
    admin_conn: Conn, downloader_pool: Pool, mapper_pool: Pool
) -> None:
    downloader = RoadDownloader()

    assert await run(downloader, downloader_pool, mapper_pool) is None

    assert downloader.calls == 0


async def test_failed_rectangle_is_retried_and_the_other_is_done(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool, mapper_pool: Pool
) -> None:
    await request(api_pool, WEST)
    await request(api_pool, EAST)
    downloader = RoadDownloader(
        fetch_errors={1: DownloadError(DownloadStatus.RATE_LIMITED, "slow down")}
    )

    result = await run(downloader, downloader_pool, mapper_pool)

    assert result is not None
    assert [r.status for r in result.rectangles] == [
        DownloadStatus.RATE_LIMITED,
        DownloadStatus.OK,
    ]
    assert await queued(admin_conn) == {tile: {("pending", 1, "rate_limited")} for tile in WEST}
    assert await fetched(admin_conn, "roads") == EAST
    assert await edge_count(admin_conn) == 1
    # The retry is not due yet.
    assert await run(downloader, downloader_pool, mapper_pool) is None


async def test_rejected_request_fails_its_tiles(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool, mapper_pool: Pool
) -> None:
    await request(api_pool, WEST)
    downloader = RoadDownloader(
        fetch_errors={1: DownloadError(DownloadStatus.INVALID_RESPONSE, "bad query")}
    )

    await run(downloader, downloader_pool, mapper_pool)

    assert await queued(admin_conn) == {tile: {("failed", 1, "invalid_response")} for tile in WEST}


async def test_mapper_failure_retries_the_stored_tiles(
    admin_conn: Conn,
    api_pool: Pool,
    downloader_pool: Pool,
    mapper_pool: Pool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await request(api_pool, WEST)
    downloader = RoadDownloader()

    with monkeypatch.context() as patch:
        patch.setattr(queries, "UPDATE_EDGES", "SELECT 1 / 0")
        result = await run(downloader, downloader_pool, mapper_pool)

    assert result is not None and result.mapped is None
    assert await queued(admin_conn) == {tile: {("pending", 1, "mapper_error")} for tile in WEST}
    assert await fetched(admin_conn, "roads") == WEST
    assert await edge_count(admin_conn) == 0

    await admin_conn.execute("UPDATE raw.pending_tiles SET next_attempt_at = now()")
    await run(downloader, downloader_pool, mapper_pool)

    assert downloader.calls == 2
    assert await queued(admin_conn) == {}
    assert await edge_count(admin_conn) == 1


async def test_queued_gap_tiles_are_done_with_their_rectangle(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool, mapper_pool: Pool
) -> None:
    await request(api_pool, GAP)
    await admin_conn.execute(
        "UPDATE raw.pending_tiles SET next_attempt_at = now() + interval '1 hour'"
    )
    await request(api_pool, WEST)
    await request(api_pool, EAST)

    result = await run(RoadDownloader(max_extra_tiles=4), downloader_pool, mapper_pool)

    assert result is not None
    assert result.tiles_claimed == 8
    assert [r.rect.area for r in result.rectangles] == [12]
    assert await queued(admin_conn) == {}
    assert await fetched(admin_conn, "roads") == WEST | GAP | EAST


async def test_area_without_features_is_done(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool, mapper_pool: Pool
) -> None:
    await request(api_pool, WEST)

    result = await run(OpenWaterDownloader(), downloader_pool, mapper_pool)

    assert result is not None and result.mapped is not None
    assert result.mapped.batches == ()
    assert await queued(admin_conn) == {}
    assert await fetched(admin_conn, "roads") == WEST


async def test_cycle_claims_at_most_the_limit(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool, mapper_pool: Pool
) -> None:
    await request(api_pool, WEST)

    result = await worker.run_once(
        [RoadDownloader()], downloader_pool.connection, mapper_pool.connection, claim_limit=3
    )

    assert result is not None and result.tiles_claimed == 3
    assert len(await queued(admin_conn)) == 1


async def listen(listener: Conn) -> None:
    await listener.execute(f"LISTEN {worker.NOTIFY_CHANNEL}")


async def test_wait_ends_when_a_tile_is_requested(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool, listener: Conn
) -> None:
    await listen(listener)
    waiting = asyncio.create_task(
        worker.wait_for_work(listener, downloader_pool.connection, RoadDownloader.layers)
    )
    await asyncio.sleep(0.2)
    assert not waiting.done()

    await request(api_pool, WEST)

    await asyncio.wait_for(waiting, timeout=5)


async def test_wait_ends_at_once_for_a_request_made_before_it(
    admin_conn: Conn, downloader_pool: Pool, listener: Conn
) -> None:
    await listen(listener)
    # Not due for an hour, so only the buffered notification can end the wait.
    await admin_conn.execute(
        """
        INSERT INTO raw.pending_tiles (layer, z, x, y, next_attempt_at)
        VALUES ('roads', 14, 8800, 4700, now() + interval '1 hour')
        """
    )

    await asyncio.wait_for(
        worker.wait_for_work(listener, downloader_pool.connection, RoadDownloader.layers), timeout=5
    )


async def test_wait_ends_when_a_retry_falls_due(
    admin_conn: Conn, downloader_pool: Pool, listener: Conn
) -> None:
    # Queued before LISTEN, so no notification reaches the listener.
    await admin_conn.execute(
        """
        INSERT INTO raw.pending_tiles (layer, z, x, y, next_attempt_at)
        VALUES ('roads', 14, 8800, 4700, now() + interval '0.5 seconds')
        """
    )
    await listen(listener)

    started = time.monotonic()
    await asyncio.wait_for(
        worker.wait_for_work(listener, downloader_pool.connection, RoadDownloader.layers), timeout=5
    )

    assert time.monotonic() - started >= 0.3


async def test_wait_returns_at_once_when_a_tile_is_due(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool, listener: Conn
) -> None:
    await request(api_pool, WEST)
    await listen(listener)

    await asyncio.wait_for(
        worker.wait_for_work(listener, downloader_pool.connection, RoadDownloader.layers), timeout=5
    )


async def eventually(check: Callable[[], Awaitable[bool]], timeout_s: float = 10) -> None:
    deadline = time.monotonic() + timeout_s
    while not await check():
        assert time.monotonic() < deadline, "condition was not met in time"
        await asyncio.sleep(0.05)


async def test_serve_resumes_interrupted_tiles_and_handles_later_requests(
    admin_conn: Conn, api_pool: Pool, downloader_pool: Pool, mapper_pool: Pool, listener: Conn
) -> None:
    async def west_fetched() -> bool:
        return await fetched(admin_conn, "roads") == WEST

    async def all_fetched() -> bool:
        return await fetched(admin_conn, "roads") == WEST | EAST

    # Left running by a worker that died.
    await request(api_pool, WEST)
    await admin_conn.execute("UPDATE raw.pending_tiles SET status = 'running'")

    serving = asyncio.create_task(
        worker.serve(
            [RoadDownloader()], downloader_pool.connection, mapper_pool.connection, listener
        )
    )
    try:
        await eventually(west_fetched)
        await request(api_pool, EAST)
        await eventually(all_fetched)
    finally:
        serving.cancel()
        with suppress(asyncio.CancelledError):
            await serving

    assert await queued(admin_conn) == {}
    assert await edge_count(admin_conn) == 2
