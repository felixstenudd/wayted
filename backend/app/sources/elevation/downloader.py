"""Fetches the height model for a rectangle of tiles and stores it cut into one raster per tile."""

from collections import OrderedDict
from dataclasses import dataclass

import httpx
from psycopg import AsyncConnection
from psycopg.rows import TupleRow

from ..tiles import Bounds, tiles_for_bounds
from .copernicus import Cell, cells_for_bounds, fetch_cell

LAYER = "elevation"

LAYER_ZOOM = "SELECT zoom FROM ref.source_layers WHERE code = %(layer)s"

# The source files are read once a store and split on their own grid, so a tile is cut from a
# few small rasters instead of the whole file, and from the same ones whatever the rectangle:
# cut to the rectangle first, their corners would move in the last digit with it and change the
# stored bytes of unchanged tiles.
CREATE_SOURCE = """
    CREATE TEMP TABLE elevation_source (n int NOT NULL, rast raster NOT NULL) ON COMMIT DROP
"""

LOAD_SOURCE = """
    INSERT INTO elevation_source (n, rast)
    SELECT f.n, c.rast
    FROM unnest(%(files)s::bytea[]) WITH ORDINALITY AS f(bytes, n)
    CROSS JOIN LATERAL ST_Tile(ST_FromGDALRaster(f.bytes), 100, 100) c(rast)
    WHERE ST_Intersects(
        ST_ConvexHull(c.rast),
        ST_Expand(ST_MakeEnvelope(%(west)s, %(south)s, %(east)s, %(north)s, 4326), 0.01)
    )
"""

# Each tile is cut one cell wider than itself on every side, from every file it reaches into.
# Files of different latitude bands have cells of different widths, so parts from another file
# than the first are put on its grid before they are joined, always in the same order so the
# result is the same to the bit. A tile whose heights did not change is not written, so the
# enricher is not woken for it.
STORE_TILES = """
    WITH tiles AS (
        SELECT t.x, t.y, ST_Transform(ST_TileEnvelope(%(z)s, t.x, t.y), 4326) AS envelope
        FROM unnest(%(xs)s::int[], %(ys)s::int[]) AS t(x, y)
    ),
    parts AS (
        SELECT t.x, t.y, s.n,
               ST_Clip(s.rast, ST_Expand(t.envelope, ST_ScaleX(s.rast), -ST_ScaleY(s.rast)))
                   AS rast
        FROM tiles t
        JOIN elevation_source s
          ON ST_Intersects(
                 ST_ConvexHull(s.rast),
                 ST_Expand(t.envelope, ST_ScaleX(s.rast), -ST_ScaleY(s.rast))
             )
    ),
    grids AS (
        SELECT DISTINCT ON (x, y) x, y, rast
        FROM parts
        ORDER BY x, y, n, ST_UpperLeftY(rast) DESC, ST_UpperLeftX(rast)
    ),
    cut AS (
        SELECT p.x, p.y,
               ST_Union(CASE WHEN ST_SameAlignment(p.rast, g.rast) THEN p.rast
                             ELSE ST_Resample(p.rast, g.rast) END
                        ORDER BY p.n, ST_UpperLeftY(p.rast) DESC, ST_UpperLeftX(p.rast)) AS rast
        FROM parts p JOIN grids g USING (x, y)
        GROUP BY p.x, p.y
    )
    INSERT INTO raw.elevation_tiles AS existing (z, x, y, rast)
    SELECT %(z)s, x, y, rast FROM cut
    ON CONFLICT (z, x, y) DO UPDATE SET rast = EXCLUDED.rast
    WHERE existing.rast::bytea IS DISTINCT FROM EXCLUDED.rast::bytea
"""


@dataclass(frozen=True, slots=True)
class ElevationData:
    bounds: Bounds
    # GeoTIFFs of the cells bounds reaches into that have land; none over open sea
    files: tuple[bytes, ...]


class ElevationDownloader:
    """
    Downloads whole 1 by 1 degree files of the height model and keeps the last few, since the
    rectangles the worker claims are much smaller and mostly lie in the same file.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        max_tiles: int = 64,
        max_extra_tiles: int = 16,
        cached_files: int = 4,
    ) -> None:
        self.client = client
        self.layers: tuple[str, ...] = (LAYER,)
        self.max_tiles = max_tiles
        self.max_extra_tiles = max_extra_tiles
        self.cached_files = cached_files
        self._files: OrderedDict[Cell, bytes | None] = OrderedDict()

    async def fetch(self, bounds: Bounds) -> ElevationData:
        files = [await self._file(cell) for cell in cells_for_bounds(bounds)]
        return ElevationData(bounds, tuple(f for f in files if f is not None))

    async def store(self, conn: AsyncConnection[TupleRow], payload: ElevationData) -> None:
        if not payload.files:
            return
        cur = await conn.execute(LAYER_ZOOM, {"layer": LAYER})
        row = await cur.fetchone()
        assert row is not None
        zoom: int = row[0]
        tiles = sorted(tiles_for_bounds(payload.bounds, zoom), key=lambda t: (t.y, t.x))
        await conn.execute(CREATE_SOURCE)
        bounds = payload.bounds
        await conn.execute(
            LOAD_SOURCE,
            {
                "files": list(payload.files),
                "west": bounds.west,
                "south": bounds.south,
                "east": bounds.east,
                "north": bounds.north,
            },
        )
        await conn.execute(
            STORE_TILES, {"z": zoom, "xs": [t.x for t in tiles], "ys": [t.y for t in tiles]}
        )

    async def _file(self, cell: Cell) -> bytes | None:
        if cell in self._files:
            self._files.move_to_end(cell)
            return self._files[cell]
        data = await fetch_cell(self.client, cell)
        self._files[cell] = data
        if len(self._files) > self.cached_files:
            self._files.popitem(last=False)
        return data
