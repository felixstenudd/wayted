import httpx
import psycopg
import pytest
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from app.sources.osm import ROADS, OsmData, OsmDownloader, OsmNode, OsmWay

pytestmark = pytest.mark.db

Pool = AsyncConnectionPool[AsyncConnection[TupleRow]]

BEFORE = OsmData(
    nodes=[
        OsmNode(id=1, tags={}, lon=18.0, lat=59.0),
        OsmNode(id=2, tags={}, lon=18.001, lat=59.0),
    ],
    ways=[
        OsmWay(id=10, tags={"highway": "path"}, node_ids=[1, 2]),
        OsmWay(id=11, tags={"highway": "path"}, node_ids=[2, 1]),
    ],
    relations=[],
)


async def store(pool: Pool, data: OsmData) -> None:
    async with httpx.AsyncClient() as client, pool.connection() as conn:
        await OsmDownloader(client, [ROADS]).store(conn, data)


async def queues(conn: AsyncConnection[TupleRow]) -> tuple[list[int], list[int]]:
    cur = await conn.execute(
        """
        SELECT
            coalesce((SELECT array_agg(way_id ORDER BY way_id) FROM graph.pending_ways), '{}'),
            coalesce((SELECT array_agg(node_id ORDER BY node_id) FROM graph.pending_nodes), '{}')
        """
    )
    row = await cur.fetchone()
    assert row is not None
    return row[0], row[1]


async def test_stored_ways_are_queued(
    admin_conn: AsyncConnection[TupleRow], downloader_pool: Pool
) -> None:
    await store(downloader_pool, BEFORE)

    assert await queues(admin_conn) == ([10, 11], [])


async def test_storing_unchanged_data_queues_nothing(
    admin_conn: AsyncConnection[TupleRow], downloader_pool: Pool
) -> None:
    await store(downloader_pool, BEFORE)
    await admin_conn.execute("TRUNCATE graph.pending_ways, graph.pending_nodes")

    await store(downloader_pool, BEFORE)

    assert await queues(admin_conn) == ([], [])


async def test_changed_ways_and_moved_nodes_are_queued(
    admin_conn: AsyncConnection[TupleRow], downloader_pool: Pool
) -> None:
    await store(downloader_pool, BEFORE)
    await admin_conn.execute("TRUNCATE graph.pending_ways, graph.pending_nodes")
    after = OsmData(
        nodes=[
            OsmNode(id=1, tags={"barrier": "gate"}, lon=18.0, lat=59.0),
            OsmNode(id=2, tags={}, lon=18.002, lat=59.0),
        ],
        ways=[
            OsmWay(id=10, tags={"highway": "footway"}, node_ids=[1, 2]),
            OsmWay(id=11, tags={"highway": "path"}, node_ids=[2, 1]),
        ],
        relations=[],
    )

    await store(downloader_pool, after)

    # Node 1 only changed its tags, which does not change the graph.
    assert await queues(admin_conn) == ([10], [2])


async def test_deleted_ways_are_queued(
    admin_conn: AsyncConnection[TupleRow], downloader_pool: Pool
) -> None:
    await store(downloader_pool, BEFORE)
    await admin_conn.execute("TRUNCATE graph.pending_ways")

    async with downloader_pool.connection() as conn:
        await conn.execute("DELETE FROM raw.osm_ways WHERE id = 11")

    assert await queues(admin_conn) == ([11], [])


async def test_downloader_cannot_read_the_graph(downloader_pool: Pool) -> None:
    async with downloader_pool.connection() as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            await conn.execute("SELECT 1 FROM graph.edges")
