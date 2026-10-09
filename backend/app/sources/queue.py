"""
The queue of tiles waiting to be fetched and mapped. Anything that needs data for an area calls
request_area; the worker claims the rows and settles them once the tiles are in the graph.
"""

from collections import defaultdict
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from psycopg import AsyncConnection
from psycopg.rows import TupleRow

from .downloader import DownloadStatus, RectangleResult
from .osm.layers import LAYERS
from .tiles import Bounds, Tile, tiles_for_bounds

# Only queue layers that has a downloader implemented
LAYER_CODES = tuple(layer.code for layer in LAYERS)

type Status = Literal["pending", "running", "failed"]

MAX_ATTEMPTS = 10
MAPPER_ERROR = "mapper_error"
# INVALID_RESPONSE is left out: the same query would be rejected again.
RETRYABLE = frozenset(
    {
        DownloadStatus.RATE_LIMITED,
        DownloadStatus.TIMEOUT,
        DownloadStatus.SOURCE_ERROR,
        DownloadStatus.STORAGE_ERROR,
    }
)

LAYER_ZOOMS = "SELECT code, zoom FROM ref.source_layers WHERE code = ANY(%s)"

# A failed tile is queued again whether or not it is fetched: it may be in raw but not the graph.
RESET_FAILED = """
    UPDATE raw.pending_tiles AS queued
    SET status = 'pending', attempts = 0, requested_at = now(), next_attempt_at = now(),
        last_status = NULL, last_message = NULL
    FROM unnest(%(xs)s::int[], %(ys)s::int[]) AS tile (x, y)
    WHERE (queued.layer, queued.z, queued.x, queued.y) = (%(layer)s, %(z)s, tile.x, tile.y)
      AND queued.status = 'failed'
"""

# DO NOTHING, not DO UPDATE: that would lock every row already queued until the caller commits,
# and the worker claims and settles those rows.
QUEUE_TILES = """
    INSERT INTO raw.pending_tiles (layer, z, x, y)
    SELECT %(layer)s, %(z)s, tile.x, tile.y
    FROM unnest(%(xs)s::int[], %(ys)s::int[]) AS tile (x, y)
    WHERE %(refetch)s OR NOT EXISTS (
        SELECT FROM raw.fetched_tiles AS fetched
        WHERE (fetched.layer, fetched.z, fetched.x, fetched.y)
            = (%(layer)s, %(z)s, tile.x, tile.y)
          AND fetched.expires_at > now()
    )
    ON CONFLICT (layer, z, x, y) DO NOTHING
"""

# Claims whole tiles: a downloader fetches every layer of a tile in one request.
CLAIM = """
    WITH due AS (
        SELECT z, x, y
        FROM raw.pending_tiles
        WHERE status = 'pending' AND next_attempt_at <= now() AND layer = ANY(%(layers)s)
        GROUP BY z, x, y
        ORDER BY min(requested_at), z, y, x
        LIMIT %(limit)s
    )
    UPDATE raw.pending_tiles AS queued
    SET status = 'running'
    FROM due
    WHERE (queued.z, queued.x, queued.y) = (due.z, due.x, due.y)
      AND queued.status = 'pending' AND queued.layer = ANY(%(layers)s)
    RETURNING queued.layer, queued.z, queued.x, queued.y
"""

IN_RECTANGLE = """
    queued.layer = ANY(%(layers)s) AND queued.z = %(z)s
    AND queued.x BETWEEN %(x_min)s AND %(x_max)s AND queued.y BETWEEN %(y_min)s AND %(y_max)s
"""

# Every queued tile in the rectangle was fetched, also those that were not claimed.
DELETE_FETCHED = f"""
    DELETE FROM raw.pending_tiles AS queued
    USING raw.fetched_tiles AS fetched
    WHERE (fetched.layer, fetched.z, fetched.x, fetched.y)
        = (queued.layer, queued.z, queued.x, queued.y)
      AND queued.requested_at <= fetched.fetched_at
      AND {IN_RECTANGLE}
"""

RETRY_OR_FAIL = f"""
    UPDATE raw.pending_tiles AS queued
    SET attempts = attempts + 1,
        status = CASE WHEN %(retry)s AND attempts + 1 < %(max_attempts)s
                      THEN 'pending' ELSE 'failed' END,
        next_attempt_at = now() + (attempts + 1) * interval '1 minute',
        last_status = %(status)s,
        last_message = %(message)s
    WHERE queued.status = 'running' AND {IN_RECTANGLE}
"""

RESET_RUNNING = "UPDATE raw.pending_tiles SET status = 'pending' WHERE status = 'running'"

SECONDS_UNTIL_DUE = """
    SELECT EXTRACT(epoch FROM min(next_attempt_at) - now())::float8
    FROM raw.pending_tiles
    WHERE status = 'pending' AND layer = ANY(%(layers)s)
"""

QUEUED_TILES = """
    SELECT layer, z, x, y, requested_at, status, attempts, next_attempt_at,
           last_status, last_message
    FROM raw.pending_tiles
    ORDER BY requested_at, layer, z, y, x
"""


@dataclass(frozen=True, slots=True)
class QueuedTile:
    layer: str
    tile: Tile
    requested_at: datetime
    status: Status
    attempts: int
    next_attempt_at: datetime
    # how the last attempt failed; None before the first failure
    last_status: str | None
    last_message: str | None


async def request_area(
    conn: AsyncConnection[TupleRow], bounds: Bounds, refetch: bool = False
) -> int:
    """
    Queue the tiles covering bounds that are not fetched, for every layer. Returns the number of
    rows queued. Runs in the caller's transaction.

    A tile already waiting or being fetched is left alone, a failed one is queued again. With
    refetch set to true, tiles that are fetched and not expired are queued too.
    """
    cur = await conn.execute(LAYER_ZOOMS, (list(LAYER_CODES),))
    queued = 0
    for layer, zoom in sorted(await cur.fetchall()):
        tiles = sorted(tiles_for_bounds(bounds, zoom), key=lambda t: (t.y, t.x))
        params = {
            "layer": layer,
            "z": zoom,
            "xs": [t.x for t in tiles],
            "ys": [t.y for t in tiles],
            "refetch": refetch,
        }
        queued += (await conn.execute(RESET_FAILED, params)).rowcount
        queued += (await conn.execute(QUEUE_TILES, params)).rowcount
    return queued


async def claim(
    conn: AsyncConnection[TupleRow], layers: Collection[str], limit: int
) -> dict[str, set[Tile]]:
    """Mark up to limit due tiles as running, oldest request first. Returns them by layer."""
    cur = await conn.execute(CLAIM, {"layers": list(layers), "limit": limit})
    claimed: defaultdict[str, set[Tile]] = defaultdict(set)
    for layer, z, x, y in await cur.fetchall():
        claimed[layer].add(Tile(x=x, y=y, z=z))
    return dict(claimed)


async def settle(
    conn: AsyncConnection[TupleRow],
    layers: Collection[str],
    results: Sequence[RectangleResult],
    mapper_error: str | None = None,
) -> None:
    """
    Record how one downloader's rectangles went. Runs in the caller's transaction.

    With a mapper_error, stored rectangles are retried: their tiles are in raw but not the graph.
    """
    for result in results:
        rect = result.rect
        in_rectangle = {
            "layers": list(layers),
            "z": rect.z,
            "x_min": rect.x_min,
            "x_max": rect.x_max,
            "y_min": rect.y_min,
            "y_max": rect.y_max,
        }
        if result.status is DownloadStatus.OK and mapper_error is None:
            await conn.execute(DELETE_FETCHED, in_rectangle)
            continue
        if result.status is DownloadStatus.OK:
            status, message, retry = MAPPER_ERROR, mapper_error, True
        else:
            status, message, retry = result.status.value, result.message, result.status in RETRYABLE
        await conn.execute(
            RETRY_OR_FAIL,
            {
                **in_rectangle,
                "status": status,
                "message": message,
                "retry": retry,
                "max_attempts": MAX_ATTEMPTS,
            },
        )


async def reset_running(conn: AsyncConnection[TupleRow]) -> int:
    """Return rows left running by a worker that died to the queue. Only one worker runs."""
    return (await conn.execute(RESET_RUNNING)).rowcount


async def seconds_until_due(
    conn: AsyncConnection[TupleRow], layers: Collection[str]
) -> float | None:
    """
    Seconds until the next pending tile may be claimed; None when nothing is pending. Counts
    the same layers as claim, or a row claim never takes would end every wait at once.
    """
    cur = await conn.execute(SECONDS_UNTIL_DUE, {"layers": list(layers)})
    row = await cur.fetchone()
    assert row is not None
    seconds: float | None = row[0]
    return None if seconds is None else max(seconds, 0.0)


async def queued_tiles(conn: AsyncConnection[TupleRow]) -> list[QueuedTile]:
    """Every queued tile, oldest request first."""
    cur = await conn.execute(QUEUED_TILES)
    return [
        QueuedTile(layer, Tile(x=x, y=y, z=z), *state)
        for layer, z, x, y, *state in await cur.fetchall()
    ]
