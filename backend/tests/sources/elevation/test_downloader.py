import httpx
import pytest
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from app.sources import download_tiles
from app.sources.elevation import Cell, ElevationData, ElevationDownloader
from app.sources.tiles import Tile, TileRect

pytestmark = pytest.mark.db

type Conn = AsyncConnection[TupleRow]
type Pool = AsyncConnectionPool[Conn]

# Two zoom-14 tiles side by side; 18.0 runs through the western one.
WEST = Tile.from_lat_lon(59.31, 18.0, 14)
EAST = Tile(x=WEST.x + 1, y=WEST.y, z=14)
RECT = TileRect(z=14, x_min=WEST.x, y_min=WEST.y, x_max=EAST.x, y_max=WEST.y)


async def geotiff(
    conn: Conn,
    west: float,
    north: float,
    cells: tuple[int, int],
    cell: tuple[float, float],
    heights: str,
) -> bytes:
    """A GeoTIFF from (west, north) of cells (columns, rows) of cell (width, height) degrees,
    each as high as the map algebra expression heights, such as '[rast.x]' for its column."""
    cur = await conn.execute(
        """
        SELECT ST_AsGDALRaster(
            ST_MapAlgebra(
                ST_AddBand(
                    ST_MakeEmptyRaster(%(columns)s, %(rows)s, %(west)s, %(north)s,
                                       %(width)s, -%(height)s, 0, 0, 4326),
                    '32BF'::text, 0, -32767
                ),
                1, '32BF', %(heights)s
            ),
            'GTiff'
        )
        """,
        {
            "columns": cells[0],
            "rows": cells[1],
            "west": west,
            "north": north,
            "width": cell[0],
            "height": cell[1],
            "heights": heights,
        },
    )
    row = await cur.fetchone()
    assert row is not None
    data: bytes = row[0]
    return data


async def rising_east(conn: Conn) -> bytes:
    """Covers both tiles in cells of 0.0005 by 0.00025 degrees, one metre higher each column."""
    return await geotiff(conn, 17.99, 59.33, (120, 160), (0.0005, 0.00025), "[rast.x]")


async def store(pool: Pool, data: ElevationData) -> None:
    async with httpx.AsyncClient() as client, pool.connection() as conn:
        await ElevationDownloader(client).store(conn, data)


async def height_at(conn: Conn, tile: Tile, lon: float, lat: float) -> float | None:
    cur = await conn.execute(
        """
        SELECT ST_Value(rast, ST_Point(%s, %s, 4326)) FROM raw.elevation_tiles
        WHERE (z, x, y) = (%s, %s, %s)
        """,
        (lon, lat, tile.z, tile.x, tile.y),
    )
    row = await cur.fetchone()
    return None if row is None else row[0]


async def queued(conn: Conn) -> list[tuple[int, int, int]]:
    cur = await conn.execute("SELECT z, x, y FROM enrich.pending_elevation ORDER BY id")
    return [(z, x, y) for z, x, y in await cur.fetchall()]


async def test_each_tile_gets_its_own_raster_a_cell_wider_than_itself(
    admin_conn: Conn, downloader_pool: Pool
) -> None:
    await store(downloader_pool, ElevationData(RECT.bounds, (await rising_east(admin_conn),)))

    cur = await admin_conn.execute(
        """
        SELECT x, y,
               ST_Contains(ST_ConvexHull(rast), ST_Expand(envelope, 0.00025, 0.000125)),
               ST_Contains(ST_Expand(envelope, 0.0011, 0.00051), ST_ConvexHull(rast))
        FROM raw.elevation_tiles,
             LATERAL (SELECT ST_Transform(ST_TileEnvelope(z, x, y), 4326) AS envelope) e
        ORDER BY x
        """
    )
    rows = await cur.fetchall()

    assert rows == [(WEST.x, WEST.y, True, True), (EAST.x, EAST.y, True, True)]
    # The cell 18.0005 to 18.001 is column 22 from 17.99.
    assert await height_at(admin_conn, WEST, 18.0007, 59.31) == 22
    assert sorted(await queued(admin_conn)) == [(14, WEST.x, WEST.y), (14, EAST.x, EAST.y)]


async def test_storing_the_same_heights_again_wakes_nothing(
    admin_conn: Conn, downloader_pool: Pool
) -> None:
    rising = await rising_east(admin_conn)
    await store(downloader_pool, ElevationData(RECT.bounds, (rising,)))
    await admin_conn.execute("TRUNCATE enrich.pending_elevation")

    await store(downloader_pool, ElevationData(RECT.bounds, (rising,)))
    assert await queued(admin_conn) == []

    flat = await geotiff(admin_conn, 17.99, 59.33, (120, 160), (0.0005, 0.00025), "7")
    await store(downloader_pool, ElevationData(RECT.bounds, (flat,)))
    assert sorted(await queued(admin_conn)) == [(14, WEST.x, WEST.y), (14, EAST.x, EAST.y)]
    assert await height_at(admin_conn, WEST, 18.0007, 59.31) == 7


async def test_a_tile_stored_again_with_another_rectangle_wakes_nothing(
    admin_conn: Conn, downloader_pool: Pool
) -> None:
    rising = await rising_east(admin_conn)
    await store(downloader_pool, ElevationData(EAST.bounds, (rising,)))
    await admin_conn.execute("TRUNCATE enrich.pending_elevation")

    await store(downloader_pool, ElevationData(RECT.bounds, (rising,)))

    assert await queued(admin_conn) == [(14, WEST.x, WEST.y)]


async def test_a_tile_across_two_files_with_other_cell_widths_has_both(
    admin_conn: Conn, downloader_pool: Pool
) -> None:
    # The western file ends at 18.0, inside the western tile, where the eastern one begins with
    # cells twice as wide, as between latitude bands.
    west_file = await geotiff(admin_conn, 17.98, 59.33, (40, 160), (0.0005, 0.00025), "10")
    east_file = await geotiff(admin_conn, 18.0, 59.33, (20, 160), (0.001, 0.00025), "20")

    await store(downloader_pool, ElevationData(WEST.bounds, (west_file, east_file)))

    assert await height_at(admin_conn, WEST, 17.999, 59.31) == 10
    assert await height_at(admin_conn, WEST, 18.01, 59.31) == 20


async def test_open_sea_stores_nothing_but_counts_as_fetched(
    admin_conn: Conn, downloader_pool: Pool
) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(404))
    ) as client:
        results = await download_tiles(
            ElevationDownloader(client), {WEST, EAST}, downloader_pool.connection
        )

    cur = await admin_conn.execute("SELECT count(*) FROM raw.elevation_tiles")
    stored = await cur.fetchone()
    cur = await admin_conn.execute("SELECT layer, x FROM raw.fetched_tiles ORDER BY x")
    fetched = await cur.fetchall()

    assert [r.status.value for r in results] == ["ok"]
    assert stored == (0,)
    assert fetched == [("elevation", WEST.x), ("elevation", EAST.x)]


async def test_downloaded_files_are_stored_through_the_worker(
    admin_conn: Conn, downloader_pool: Pool
) -> None:
    rising = await rising_east(admin_conn)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, content=rising)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await download_tiles(ElevationDownloader(client), {EAST}, downloader_pool.connection)

    # The tile lies in the cell N59 E018 alone.
    assert seen == [Cell(59, 18).url]
    # The cell 18.03 to 18.0305 is column 81 from 17.99.
    assert await height_at(admin_conn, EAST, 18.0302, 59.31) == 81
