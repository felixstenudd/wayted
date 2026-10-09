"""
The queue of tiles waiting to be fetched and mapped. Anything that needs data for an area calls
request_area; the worker claims the rows and settles them once the tiles are in the graph.
"""

from collections import defaultdict
from collections.abc import Collection, Sequence

from psycopg import AsyncConnection
from psycopg.rows import TupleRow

from .downloader import DownloadStatus, RectangleResult
from .osm.layers import LAYERS
from .tiles import Bounds, Tile, tiles_for_bounds

# Only queue layers that has a downloader implemented
LAYER_CODES = tuple(layer.code for layer in LAYERS)

MAX_ATTEMPTS = 5
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

QUEUE_TILES = """
    INSERT INTO raw.pending_tiles AS queued (layer, z, x, y)
    SELECT %(layer)s, %(z)s, tile.x, tile.y
    FROM unnest(%(xs)s::int[], %(ys)s::int[]) AS tile (x, y)
    WHERE %(refetch)s OR NOT EXISTS (
        SELECT FROM raw.fetched_tiles AS fetched
        WHERE (fetched.layer, fetched.z, fetched.x, fetched.y)
            = (%(layer)s, %(z)s, tile.x, tile.y)
          AND fetched.expires_at > now()
    )
    ON CONFLICT (layer, z, x, y) DO UPDATE
    SET status = 'pending', attempts = 0, requested_at = now(), next_attempt_at = now(),
        last_status = NULL, last_message = NULL
    WHERE queued.status = 'failed'
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
    layer = ANY(%(layers)s) AND z = %(z)s
    AND x BETWEEN %(x_min)s AND %(x_max)s AND y BETWEEN %(y_min)s AND %(y_max)s
"""

# Every queued tile in the rectangle was fetched, also those that were not claimed.
DELETE_FETCHED = f"DELETE FROM raw.pending_tiles WHERE {IN_RECTANGLE}"

RETRY_OR_FAIL = f"""
    UPDATE raw.pending_tiles
    SET attempts = attempts + 1,
        status = CASE WHEN %(retry)s AND attempts + 1 < %(max_attempts)s
                      THEN 'pending' ELSE 'failed' END,
        next_attempt_at = now() + (attempts + 1) * interval '1 minute',
        last_status = %(status)s,
        last_message = %(message)s
    WHERE status = 'running' AND {IN_RECTANGLE}
"""

RESET_RUNNING = "UPDATE raw.pending_tiles SET status = 'pending' WHERE status = 'running'"

SECONDS_UNTIL_DUE = """
    SELECT EXTRACT(epoch FROM min(next_attempt_at) - now())::float8
    FROM raw.pending_tiles
    WHERE status = 'pending'
"""


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
        cur = await conn.execute(
            QUEUE_TILES,
            {
                "layer": layer,
                "z": zoom,
                "xs": [t.x for t in tiles],
                "ys": [t.y for t in tiles],
                "refetch": refetch,
            },
        )
        queued += cur.rowcount
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


async def seconds_until_due(conn: AsyncConnection[TupleRow]) -> float | None:
    """Seconds until the next pending tile may be claimed; None when nothing is pending."""
    cur = await conn.execute(SECONDS_UNTIL_DUE)
    row = await cur.fetchone()
    assert row is not None
    seconds: float | None = row[0]
    return None if seconds is None else max(seconds, 0.0)
