"""Records which tiles of a layer have been fetched and until when they stay valid."""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from psycopg import AsyncConnection
from psycopg.rows import TupleRow

from .tiles import Tile

# expires_at comes from the layer's ttl in ref, so the ttl lives only in the database.
MARK_FETCHED = """
    INSERT INTO raw.fetched_tiles (layer, z, x, y, fetched_at, expires_at)
    SELECT code, %(z)s, %(x)s, %(y)s, now(), now() + ttl
    FROM ref.source_layers
    WHERE code = %(layer)s
    ON CONFLICT (layer, z, x, y) DO UPDATE
    SET fetched_at = EXCLUDED.fetched_at, expires_at = EXCLUDED.expires_at
"""

FETCHED_TILES = """
    SELECT layer, z, x, y, fetched_at, expires_at
    FROM raw.fetched_tiles
    ORDER BY fetched_at, layer, z, y, x
"""


@dataclass(frozen=True, slots=True)
class FetchedTile:
    layer: str
    tile: Tile
    fetched_at: datetime
    expires_at: datetime


async def mark_fetched(
    conn: AsyncConnection[TupleRow], layer: str, tiles: Collection[Tile]
) -> None:
    """Mark tiles as fetched now. Runs in the caller's transaction."""
    ordered = sorted(tiles, key=lambda t: (t.z, t.x, t.y))
    async with conn.cursor() as cur:
        await cur.executemany(
            MARK_FETCHED,
            [{"layer": layer, "z": t.z, "x": t.x, "y": t.y} for t in ordered],
        )


async def fetched_tiles(conn: AsyncConnection[TupleRow]) -> list[FetchedTile]:
    """Every fetched tile, oldest fetch first. Expired tiles are included."""
    cur = await conn.execute(FETCHED_TILES)
    return [
        FetchedTile(layer, Tile(x=x, y=y, z=z), fetched_at, expires_at)
        for layer, z, x, y, fetched_at, expires_at in await cur.fetchall()
    ]
