"""
The queue of tiles waiting to be fetched and mapped. Anything that needs data for an area calls
request_area; the worker claims the rows and settles them once the tiles are in the graph.
"""

from psycopg import AsyncConnection
from psycopg.rows import TupleRow

from .osm.layers import LAYERS
from .tiles import Bounds, tiles_for_bounds

# Only queue layers that has a downloader implemented
LAYER_CODES = tuple(layer.code for layer in LAYERS)

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
