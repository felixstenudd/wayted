import httpx
import psycopg
import pytest
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from app.sources.osm import PARKS, OsmData, OsmDownloader, OsmMember, OsmNode, OsmRelation, OsmWay

pytestmark = pytest.mark.db

type Conn = AsyncConnection[TupleRow]
type Pool = AsyncConnectionPool[Conn]

BEFORE = OsmData(
    nodes=[
        OsmNode(id=1, tags={}, lon=18.0, lat=59.0),
        OsmNode(id=2, tags={}, lon=18.001, lat=59.0),
        OsmNode(id=3, tags={}, lon=18.001, lat=59.001),
    ],
    ways=[OsmWay(id=10, tags={}, node_ids=[1, 2, 3, 1])],
    relations=[
        OsmRelation(
            id=30,
            tags={"leisure": "park", "type": "multipolygon"},
            members=[OsmMember(type="way", ref=10, role="outer")],
        )
    ],
)


async def store(pool: Pool, data: OsmData) -> None:
    async with httpx.AsyncClient() as client, pool.connection() as conn:
        await OsmDownloader(client, [PARKS]).store(conn, data)


async def queues(conn: Conn) -> tuple[list[int], list[int], list[int]]:
    cur = await conn.execute(
        """
        SELECT
            coalesce((SELECT array_agg(way_id ORDER BY way_id) FROM enrich.pending_ways), '{}'),
            coalesce((SELECT array_agg(relation_id ORDER BY relation_id)
                      FROM enrich.pending_relations), '{}'),
            coalesce((SELECT array_agg(node_id ORDER BY node_id) FROM enrich.pending_nodes), '{}')
        """
    )
    row = await cur.fetchone()
    assert row is not None
    return row[0], row[1], row[2]


async def empty_queues(conn: Conn) -> None:
    await conn.execute(
        "TRUNCATE enrich.pending_ways, enrich.pending_relations, enrich.pending_nodes"
    )


async def test_stored_ways_and_relations_are_queued(
    admin_conn: Conn, downloader_pool: Pool
) -> None:
    await store(downloader_pool, BEFORE)

    assert await queues(admin_conn) == ([10], [30], [])


async def test_storing_unchanged_data_queues_nothing(
    admin_conn: Conn, downloader_pool: Pool
) -> None:
    await store(downloader_pool, BEFORE)
    await empty_queues(admin_conn)

    await store(downloader_pool, BEFORE)

    assert await queues(admin_conn) == ([], [], [])


async def test_changed_relations_and_moved_nodes_are_queued(
    admin_conn: Conn, downloader_pool: Pool
) -> None:
    await store(downloader_pool, BEFORE)
    await empty_queues(admin_conn)
    after = OsmData(
        nodes=[
            OsmNode(id=1, tags={"barrier": "gate"}, lon=18.0, lat=59.0),
            OsmNode(id=2, tags={}, lon=18.002, lat=59.0),
            OsmNode(id=3, tags={}, lon=18.001, lat=59.001),
        ],
        ways=BEFORE.ways,
        relations=[
            OsmRelation(
                id=30,
                tags={"leisure": "park", "type": "multipolygon", "name": "P"},
                members=BEFORE.relations[0].members,
            )
        ],
    )

    await store(downloader_pool, after)

    # Node 1 only changed its tags, which changes no geometry.
    assert await queues(admin_conn) == ([], [30], [2])


async def test_deleted_relations_are_queued(admin_conn: Conn, downloader_pool: Pool) -> None:
    await store(downloader_pool, BEFORE)
    await empty_queues(admin_conn)

    async with downloader_pool.connection() as conn:
        await conn.execute("DELETE FROM raw.osm_relations WHERE id = 30")

    assert await queues(admin_conn) == ([], [30], [])


async def test_a_transaction_that_queues_notifies_once(
    downloader_pool: Pool, listener: Conn
) -> None:
    await listener.execute("LISTEN pending_enrichment")

    await store(downloader_pool, BEFORE)

    channels = [n.channel async for n in listener.notifies(timeout=1)]
    assert channels == ["pending_enrichment"]


async def test_mapper_queuing_an_edge_notifies(mapper_pool: Pool, listener: Conn) -> None:
    await listener.execute("LISTEN pending_enrichment")

    # The trigger function lives in enrich, a schema the mapper cannot use.
    async with mapper_pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO graph.ways (id, tags) VALUES (1, '{}');
            INSERT INTO graph.vertices (id, geom) VALUES (1, ST_Point(18, 59, 4326)),
                                                         (2, ST_Point(18.001, 59, 4326));
            INSERT INTO graph.edges (way_id, source, target, occurrence, geom, length_m,
                                     forward, backward)
            VALUES (1, 1, 2, 1, ST_MakeLine(ST_Point(18, 59, 4326), ST_Point(18.001, 59, 4326)),
                    57, '{running}', '{running}');
            INSERT INTO graph.pending_edges (edge_id) SELECT id FROM graph.edges;
            """
        )

    channels = [n.channel async for n in listener.notifies(timeout=1)]
    assert channels == ["pending_enrichment"]


# Ten by ten cells of 0.001 degrees from (18, 59) north-east, all 5 m high.
FLAT_GEOTIFF = """
    SELECT ST_AsGDALRaster(
        ST_AddBand(ST_MakeEmptyRaster(10, 10, 18.0, 59.01, 0.001, -0.001, 0, 0, 4326),
                   '32BF'::text, 5, -32767),
        'GTiff'
    )
"""

STORE_ELEVATION = """
    INSERT INTO raw.elevation_tiles (z, x, y, rast) VALUES (14, 8971, 4757, ST_FromGDALRaster(%s))
    ON CONFLICT (z, x, y) DO UPDATE SET rast = EXCLUDED.rast
"""


async def test_stored_elevation_tiles_are_queued_and_readable_by_the_enricher(
    admin_conn: Conn, downloader_pool: Pool, enricher_pool: Pool
) -> None:
    cur = await admin_conn.execute(FLAT_GEOTIFF)
    row = await cur.fetchone()
    assert row is not None
    geotiff = row[0]

    # The downloader reads GeoTIFF itself, so the format is allowed for every role.
    async with downloader_pool.connection() as conn:
        await conn.execute(STORE_ELEVATION, (geotiff,))
        await conn.execute(STORE_ELEVATION, (geotiff,))
    async with enricher_pool.connection() as conn:
        cur = await conn.execute(
            "SELECT ST_Value(rast, ST_Point(18.0045, 59.0055, 4326)) FROM raw.elevation_tiles"
        )
        height = await cur.fetchone()
    cur = await admin_conn.execute("SELECT z, x, y FROM enrich.pending_elevation ORDER BY id")
    queued = await cur.fetchall()

    assert height == (5,)
    assert queued == [(14, 8971, 4757), (14, 8971, 4757)]


async def test_storing_an_elevation_tile_notifies(
    admin_conn: Conn, downloader_pool: Pool, listener: Conn
) -> None:
    cur = await admin_conn.execute(FLAT_GEOTIFF)
    row = await cur.fetchone()
    assert row is not None
    await listener.execute("LISTEN pending_enrichment")

    async with downloader_pool.connection() as conn:
        await conn.execute(STORE_ELEVATION, (row[0],))

    channels = [n.channel async for n in listener.notifies(timeout=1)]
    assert channels == ["pending_enrichment"]


@pytest.mark.parametrize(
    ("lon", "lat", "srid"),
    [(18.07, 59.33, 32634), (-74.0, 40.7, 32618), (18.4, -33.9, 32734), (180.0, 10.0, 32660)],
)
async def test_utm_srid_is_the_zone_of_the_centre(
    admin_conn: Conn, lon: float, lat: float, srid: int
) -> None:
    cur = await admin_conn.execute("SELECT enrich.utm_srid(ST_Point(%s, %s, 4326))", (lon, lat))
    assert await cur.fetchone() == (srid,)


@pytest.mark.parametrize("lat", [0.0, 59.3, 69.0])
async def test_expand_m_grows_the_box_by_at_least_the_distance(
    admin_conn: Conn, lat: float
) -> None:
    cur = await admin_conn.execute(
        """
        WITH p AS (SELECT ST_Point(18, %(lat)s, 4326) AS geom)
        SELECT ST_Distance(p.geom::geography, ST_Point(ST_XMax(b), %(lat)s, 4326)::geography),
               ST_Distance(p.geom::geography, ST_Point(18, ST_YMax(b), 4326)::geography)
        FROM p, enrich.expand_m(p.geom, 25) AS b
        """,
        {"lat": lat},
    )
    row = await cur.fetchone()
    assert row is not None
    east_m, north_m = row
    assert 25 <= east_m < 25.3
    assert 25 <= north_m < 25.3


async def test_enricher_may_update_only_scores(admin_conn: Conn, enricher_pool: Pool) -> None:
    async with enricher_pool.connection() as conn:
        await conn.execute("UPDATE graph.edges SET scores = '{}'")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            await conn.execute("UPDATE graph.edges SET length_m = 0")


async def test_enricher_cannot_write_raw_or_the_graph_tables(enricher_pool: Pool) -> None:
    for statement in (
        "DELETE FROM raw.osm_ways",
        "DELETE FROM raw.elevation_tiles",
        "DELETE FROM graph.ways",
        "DELETE FROM graph.pending_ways",
    ):
        async with enricher_pool.connection() as conn:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                await conn.execute(statement)


async def test_enricher_claims_and_queues_edges(enricher_pool: Pool) -> None:
    async with enricher_pool.connection() as conn:
        await conn.execute("DELETE FROM graph.pending_edges")
        await conn.execute("INSERT INTO graph.pending_edges (edge_id) SELECT id FROM graph.edges")
