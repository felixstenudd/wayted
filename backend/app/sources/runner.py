"""Runs a downloader over a set of tiles: plans requests, fetches, stores and marks tiles."""

import asyncio
from collections.abc import Collection

import httpx
import psycopg

from app.db import Connect

from .downloader import Downloader, DownloadError, DownloadStatus, RectangleResult
from .planning import plan_rectangles
from .registry import mark_fetched
from .tiles import Tile, TileRect


async def download_tiles[P](
    downloader: Downloader[P],
    tiles: Collection[Tile],
    connect: Connect,
) -> list[RectangleResult]:
    """
    Fetch and store the tiles, one request per planned rectangle and up to the downloader's
    max_requests at once. Results are in the planned order.

    Every tile inside a stored rectangle is marked fetched for every layer of the downloader,
    including tiles that were only fetched to join clusters. A failed rectangle commits nothing
    and does not stop the others.
    """
    await _check_zoom(downloader.layers, tiles, connect)
    rects = await asyncio.to_thread(
        plan_rectangles, tiles, downloader.max_extra_tiles, downloader.max_tiles
    )
    slots = asyncio.Semaphore(downloader.max_requests)
    try:
        async with asyncio.TaskGroup() as group:
            tasks = [
                group.create_task(_download_rect(downloader, rect, slots, connect))
                for rect in rects
            ]
    except ExceptionGroup as e:
        raise e.exceptions[0] from None
    return [task.result() for task in tasks]


async def _check_zoom(layers: tuple[str, ...], tiles: Collection[Tile], connect: Connect) -> None:
    if not layers:
        raise ValueError("A downloader must serve at least one layer.")
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT code, zoom FROM ref.source_layers WHERE code = ANY(%s)", (list(layers),)
        )
        zooms: dict[str, int] = dict(await cur.fetchall())
    unknown = set(layers) - zooms.keys()
    if unknown:
        raise ValueError(f"Unknown layers {sorted(unknown)}.")
    # One request serves every layer, so they have to share a tile grid.
    if len(set(zooms.values())) != 1:
        raise ValueError(f"Layers fetched together must share a zoom level; got {zooms}.")
    zoom = next(iter(zooms.values()))
    if any(tile.z != zoom for tile in tiles):
        raise ValueError(f"Layers {list(layers)} are fetched at zoom {zoom}; got other zooms.")


async def _download_rect[P](
    downloader: Downloader[P], rect: TileRect, slots: asyncio.Semaphore, connect: Connect
) -> RectangleResult:
    try:
        async with slots:
            payload = await downloader.fetch(rect.bounds)
        async with connect() as conn, conn.transaction():
            await downloader.store(conn, payload)
            for layer in downloader.layers:
                await mark_fetched(conn, layer, rect.tiles())
    except DownloadError as e:
        return RectangleResult(rect, e.status, e.message)
    except httpx.TimeoutException as e:
        return RectangleResult(rect, DownloadStatus.TIMEOUT, str(e) or type(e).__name__)
    except httpx.RequestError as e:
        return RectangleResult(rect, DownloadStatus.SOURCE_ERROR, str(e) or type(e).__name__)
    except psycopg.Error as e:
        return RectangleResult(rect, DownloadStatus.STORAGE_ERROR, str(e))
    return RectangleResult(rect, DownloadStatus.OK, None)
