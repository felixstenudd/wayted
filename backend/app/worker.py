"""
Background process that claims pending tiles and runs fetching and
graph building for them.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import psycopg

from app.db import Connect
from app.graph import MapResult, map_pending
from app.sources import Downloader, RectangleResult, Tile, download_tiles, queue

log = logging.getLogger("wayted.worker")

# Tiles per cycle, the size of one request rectangle. Tiles are ready only when their
#  whole cycle is mapped, so a larger number makes everything queued behind it wait longer.
CLAIM_LIMIT = 64


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
