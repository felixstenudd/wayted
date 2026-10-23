import asyncio
import threading
from typing import TypeAlias

import httpx
import pytest
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from app.sources import runner
from app.sources.downloader import DownloadError, DownloadStatus
from app.sources.planning import plan_rectangles
from app.sources.runner import download_tiles
from app.sources.tiles import Bounds, Tile, TileRect

pytestmark = pytest.mark.db

Pool: TypeAlias = AsyncConnectionPool[AsyncConnection[TupleRow]]  # noqa: UP040

# Two 2x2 clusters with a 2-column gap between them: merging them costs 4 extra tiles.
WEST = {Tile(x=x, y=y, z=14) for x in (8800, 8801) for y in (4700, 4701)}
EAST = {Tile(x=x, y=y, z=14) for x in (8804, 8805) for y in (4700, 4701)}
FAR = {Tile(x=x, y=y, z=14) for x in (8808, 8809) for y in (4700, 4701)}


class FakeDownloader:
    """Writes one way per rectangle; fetch and store can be told to fail."""

    def __init__(
        self,
        layers: tuple[str, ...] = ("roads",),
        max_extra_tiles: int = 0,
        max_tiles: int = 64,
        max_requests: int = 1,
        fetch_errors: dict[int, Exception] | None = None,
        fail_store: bool = False,
    ) -> None:
        self.layers = layers
        self.max_extra_tiles = max_extra_tiles
        self.max_tiles = max_tiles
        self.max_requests = max_requests
        self.fetch_errors = fetch_errors or {}
        self.fail_store = fail_store
        self.calls = 0

    async def fetch(self, bounds: Bounds) -> int:
        self.calls += 1
        if self.calls in self.fetch_errors:
            raise self.fetch_errors[self.calls]
        return self.calls

    async def store(self, conn: AsyncConnection[TupleRow], payload: int) -> None:
        await conn.execute(
            "INSERT INTO raw.osm_ways (id, tags, node_ids) VALUES (%s, '{}', '{1, 2}')", (payload,)
        )
        if self.fail_store:
            await conn.execute("SELECT 1 / 0")


async def fetched_tiles(conn: AsyncConnection[TupleRow], layer: str = "roads") -> set[Tile]:
    cur = await conn.execute("SELECT x, y, z FROM raw.fetched_tiles WHERE layer = %s", (layer,))
    return {Tile(x=x, y=y, z=z) for x, y, z in await cur.fetchall()}


async def way_ids(conn: AsyncConnection[TupleRow]) -> list[int]:
    cur = await conn.execute("SELECT id FROM raw.osm_ways ORDER BY id")
    return [way_id for (way_id,) in await cur.fetchall()]


async def test_merged_clusters_mark_gap_tiles_too(
    admin_conn: AsyncConnection[TupleRow], downloader_pool: Pool
) -> None:
    results = await download_tiles(
        FakeDownloader(max_extra_tiles=4), WEST | EAST, downloader_pool.connection
    )

    rect = TileRect(z=14, x_min=8800, y_min=4700, x_max=8805, y_max=4701)
    assert [(r.rect, r.status, r.message) for r in results] == [(rect, DownloadStatus.OK, None)]
    assert await fetched_tiles(admin_conn) == rect.tiles()
    assert await way_ids(admin_conn) == [1]


async def test_one_request_marks_every_layer(
    admin_conn: AsyncConnection[TupleRow], downloader_pool: Pool
) -> None:
    downloader = FakeDownloader(layers=("roads", "parks"))
    results = await download_tiles(downloader, WEST, downloader_pool.connection)

    assert [r.status for r in results] == [DownloadStatus.OK]
    assert downloader.calls == 1
    assert await fetched_tiles(admin_conn, "roads") == WEST
    assert await fetched_tiles(admin_conn, "parks") == WEST


async def test_failed_rectangle_does_not_affect_the_others(
    admin_conn: AsyncConnection[TupleRow], downloader_pool: Pool
) -> None:
    downloader = FakeDownloader(
        fetch_errors={1: DownloadError(DownloadStatus.RATE_LIMITED, "slow down")}
    )
    results = await download_tiles(downloader, WEST | EAST, downloader_pool.connection)

    assert [(r.status, r.message) for r in results] == [
        (DownloadStatus.RATE_LIMITED, "slow down"),
        (DownloadStatus.OK, None),
    ]
    assert await fetched_tiles(admin_conn) == EAST
    assert await way_ids(admin_conn) == [2]


class SlowDownloader(FakeDownloader):
    """
    Each fetch takes the seconds given for its call number and each store store_s; counts
    rectangles from the start of their fetch to the end of their store.
    """

    def __init__(self, seconds: dict[int, float], max_requests: int, store_s: float = 0) -> None:
        super().__init__(max_requests=max_requests)
        self.seconds = seconds
        self.store_s = store_s
        self.in_flight = 0
        self.most_in_flight = 0

    async def fetch(self, bounds: Bounds) -> int:
        self.in_flight += 1
        self.most_in_flight = max(self.most_in_flight, self.in_flight)
        call = await super().fetch(bounds)
        await asyncio.sleep(self.seconds.get(call, 0.01))
        return call

    async def store(self, conn: AsyncConnection[TupleRow], payload: int) -> None:
        await asyncio.sleep(self.store_s)
        await super().store(conn, payload)
        self.in_flight -= 1


async def test_rectangles_are_fetched_up_to_max_requests_at_once(
    admin_conn: AsyncConnection[TupleRow], downloader_pool: Pool
) -> None:
    downloader = SlowDownloader({1: 0.1}, max_requests=2)
    results = await download_tiles(downloader, WEST | EAST | FAR, downloader_pool.connection)

    assert downloader.most_in_flight == 2
    # The first rectangle finishes last but is still reported first.
    assert [r.rect for r in results] == plan_rectangles(WEST | EAST | FAR, 0, 64)
    assert [r.status for r in results] == [DownloadStatus.OK] * 3
    assert await fetched_tiles(admin_conn) == WEST | EAST | FAR
    assert await way_ids(admin_conn) == [1, 2, 3]


async def test_a_rectangle_keeps_its_request_until_it_is_stored(
    admin_conn: AsyncConnection[TupleRow], downloader_pool: Pool
) -> None:
    # Stores slower than fetches, as for a file already downloaded.
    downloader = SlowDownloader({}, max_requests=2, store_s=0.1)
    results = await download_tiles(downloader, WEST | EAST | FAR, downloader_pool.connection)

    assert downloader.most_in_flight == 2
    assert [r.status for r in results] == [DownloadStatus.OK] * 3


async def test_store_failure_rolls_back_data_and_tiles(
    admin_conn: AsyncConnection[TupleRow], downloader_pool: Pool
) -> None:
    downloader = FakeDownloader(layers=("roads", "parks"), fail_store=True)
    results = await download_tiles(downloader, WEST, downloader_pool.connection)

    assert [r.status for r in results] == [DownloadStatus.STORAGE_ERROR]
    assert await fetched_tiles(admin_conn, "roads") == set()
    assert await fetched_tiles(admin_conn, "parks") == set()
    assert await way_ids(admin_conn) == []


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (httpx.ReadTimeout("read timed out"), DownloadStatus.TIMEOUT),
        (httpx.ConnectError("connection refused"), DownloadStatus.SOURCE_ERROR),
        (httpx.DecodingError("broken gzip body"), DownloadStatus.SOURCE_ERROR),
        (httpx.TooManyRedirects("redirect loop"), DownloadStatus.SOURCE_ERROR),
    ],
)
async def test_http_failures_become_statuses(
    admin_conn: AsyncConnection[TupleRow],
    downloader_pool: Pool,
    error: Exception,
    status: DownloadStatus,
) -> None:
    results = await download_tiles(
        FakeDownloader(fetch_errors={1: error}), WEST, downloader_pool.connection
    )

    assert [(r.status, r.message) for r in results] == [(status, str(error))]
    assert await fetched_tiles(admin_conn) == set()


async def test_unexpected_errors_propagate(
    admin_conn: AsyncConnection[TupleRow], downloader_pool: Pool
) -> None:
    downloader = FakeDownloader(fetch_errors={1: RuntimeError("bug")})
    with pytest.raises(RuntimeError):
        await download_tiles(downloader, WEST, downloader_pool.connection)


async def test_tiles_at_another_zoom_are_rejected(
    admin_conn: AsyncConnection[TupleRow], downloader_pool: Pool
) -> None:
    with pytest.raises(ValueError):
        await download_tiles(FakeDownloader(), {Tile(x=0, y=0, z=13)}, downloader_pool.connection)


@pytest.mark.parametrize("layers", [(), ("roads", "nope")])
async def test_missing_or_unknown_layers_are_rejected(
    admin_conn: AsyncConnection[TupleRow], downloader_pool: Pool, layers: tuple[str, ...]
) -> None:
    with pytest.raises(ValueError):
        await download_tiles(FakeDownloader(layers=layers), WEST, downloader_pool.connection)


async def test_layers_at_different_zooms_are_rejected(
    admin_conn: AsyncConnection[TupleRow], downloader_pool: Pool
) -> None:
    await admin_conn.execute(
        "INSERT INTO ref.source_layers (code, zoom, ttl) VALUES ('coarse_test', 12, '1 day')"
    )
    try:
        with pytest.raises(ValueError):
            await download_tiles(
                FakeDownloader(layers=("roads", "coarse_test")), WEST, downloader_pool.connection
            )
    finally:
        await admin_conn.execute("DELETE FROM ref.source_layers WHERE code = 'coarse_test'")


class EmptyAreaDownloader(FakeDownloader):
    """An area with no features, like open water: Overpass returns no elements."""

    async def store(self, conn: AsyncConnection[TupleRow], payload: int) -> None:
        pass


async def test_area_without_features_is_still_marked(
    admin_conn: AsyncConnection[TupleRow], downloader_pool: Pool
) -> None:
    results = await download_tiles(EmptyAreaDownloader(), WEST, downloader_pool.connection)

    assert [r.status for r in results] == [DownloadStatus.OK]
    assert await fetched_tiles(admin_conn) == WEST


async def test_planning_runs_off_the_event_loop(
    admin_conn: AsyncConnection[TupleRow],
    downloader_pool: Pool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    planned_on: list[int] = []

    def recording_plan(*args: object, **kwargs: object) -> list[TileRect]:
        planned_on.append(threading.get_ident())
        return plan_rectangles(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(runner, "plan_rectangles", recording_plan)
    await download_tiles(FakeDownloader(), WEST, downloader_pool.connection)

    assert planned_on and planned_on[0] != threading.get_ident()
