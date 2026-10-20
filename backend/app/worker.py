"""
Background process that claims pending tiles and runs fetching and
graph building for them.
"""

import asyncio
import logging
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from functools import partial
from typing import Any

import psycopg
from psycopg import AsyncConnection
from psycopg.conninfo import make_conninfo
from psycopg.rows import TupleRow

from app import db
from app.db import Connect
from app.graph import MapResult, map_pending
from app.sources import Downloader, DownloadStatus, RectangleResult, Tile, download_tiles, queue
from app.sources.osm import LAYERS, OsmDownloader, new_client

log = logging.getLogger("wayted.worker")

# Tiles per cycle, the size of one request rectangle. Tiles are ready only when their
#  whole cycle is mapped, so a larger number makes everything queued behind it wait longer.
CLAIM_LIMIT = 64
NOTIFY_CHANNEL = "pending_tiles"


@dataclass(frozen=True, slots=True)
class CycleResult:
    tiles_claimed: int
    rectangles: tuple[RectangleResult, ...]
    mapped: MapResult | None  # None when the mapper failed


async def run_once(
    downloaders: Sequence[Downloader[Any]],
    connect_downloader: Connect,
    connect_mapper: Connect,
    claim_limit: int = CLAIM_LIMIT,
) -> CycleResult | None:
    """Fetch and map one batch of queued tiles. Returns None when no tile is due."""
    layers = [layer for downloader in downloaders for layer in downloader.layers]
    async with connect_downloader() as conn:
        claimed = await queue.claim(conn, layers, claim_limit)
    if not claimed:
        return None

    downloads: list[tuple[tuple[str, ...], list[RectangleResult]]] = []
    for downloader in downloaders:
        tiles: set[Tile] = set()
        for layer in downloader.layers:
            tiles |= claimed.get(layer, set())
        if tiles:
            results = await download_tiles(downloader, tiles, connect_downloader)
            downloads.append((downloader.layers, results))

    mapped: MapResult | None = None
    mapper_error: str | None = None
    try:
        mapped = await map_pending(connect_mapper)
    except psycopg.Error as e:
        mapper_error = str(e)
        log.error("mapping failed: %s", mapper_error)

    async with connect_downloader() as conn, conn.transaction():
        for downloader_layers, results in downloads:
            await queue.settle(conn, downloader_layers, results, mapper_error)

    return CycleResult(
        tiles_claimed=len(set().union(*claimed.values())),
        rectangles=tuple(result for _, results in downloads for result in results),
        mapped=mapped,
    )


async def wait_for_work(
    listener: AsyncConnection[TupleRow], connect: Connect, layers: Collection[str]
) -> None:
    """
    Return when a tile is requested or a retry falls due.

    listener must be listening on NOTIFY_CHANNEL and be used for nothing else, so a request made
    since the last wait is still buffered on it and ends this wait at once.
    """
    async with connect() as conn:
        timeout = await queue.seconds_until_due(conn, layers)
    if timeout == 0:
        return
    async for _ in listener.notifies(timeout=timeout, stop_after=1):
        pass


def _log_cycle(result: CycleResult) -> None:
    failed = [r for r in result.rectangles if r.status is not DownloadStatus.OK]
    for r in failed:
        log.warning("rectangle %s failed: %s: %s", r.rect, r.status.value, r.message)
    batches = result.mapped.batches if result.mapped else ()
    log.info(
        "cycle: %d tiles, %d rectangles ok, %d failed, edges +%d ~%d -%d",
        result.tiles_claimed,
        len(result.rectangles) - len(failed),
        len(failed),
        sum(b.edges_inserted for b in batches),
        sum(b.edges_updated for b in batches),
        sum(b.edges_deleted for b in batches),
    )


async def serve(
    downloaders: Sequence[Downloader[Any]],
    connect_downloader: Connect,
    connect_mapper: Connect,
    listener: AsyncConnection[TupleRow],
) -> None:
    """Run cycles until cancelled. listener is an autocommit connection used for nothing else."""
    layers = [layer for downloader in downloaders for layer in downloader.layers]
    async with connect_downloader() as conn:
        reset = await queue.reset_running(conn)
    # Listen before the first claim, so a request made from here on is never missed.
    await listener.execute(f"LISTEN {NOTIFY_CHANNEL}")
    log.info("worker started, %d interrupted rows back in the queue", reset)
    while True:
        result = await run_once(downloaders, connect_downloader, connect_mapper)
        if result is None:
            await wait_for_work(listener, connect_downloader, layers)
        else:
            _log_cycle(result)


async def main() -> None:
    # app.config reads the environment on import; here, so the tests can import this module.
    from app.config import (
        DOWNLOADER_ROLE,
        DOWNLOADER_ROLE_PASSWORD,
        MAPPER_ROLE,
        MAPPER_ROLE_PASSWORD,
    )

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    await db.open_pool(DOWNLOADER_ROLE, DOWNLOADER_ROLE_PASSWORD)
    await db.open_pool(MAPPER_ROLE, MAPPER_ROLE_PASSWORD)

    connect_downloader = partial(db.connection, DOWNLOADER_ROLE)
    connect_mapper = partial(db.connection, MAPPER_ROLE)
    conninfo = make_conninfo(user=DOWNLOADER_ROLE, password=DOWNLOADER_ROLE_PASSWORD)
    try:
        async with (
            new_client() as client,
            await AsyncConnection.connect(conninfo, autocommit=True) as listener,
        ):
            downloaders = [OsmDownloader(client, LAYERS)]
            await serve(downloaders, connect_downloader, connect_mapper, listener)
    finally:
        await db.close_pools()


if __name__ == "__main__":
    asyncio.run(main())
