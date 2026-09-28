import json
from pathlib import Path

import httpx
import pytest
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from app.sources.osm import PARKS, ROADS, OsmData, OsmDownloader, OsmNode, OsmWay
from app.sources.tiles import Bounds

FIXTURES = Path(__file__).parents[2] / "fixtures"
Pool = AsyncConnectionPool[AsyncConnection[TupleRow]]
BOUNDS = Bounds(west=18.0, south=59.0, east=18.1, north=59.1)


def downloader_answering(body: object, seen: list[httpx.Request]) -> OsmDownloader:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=body)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OsmDownloader(client, [ROADS, PARKS])


def test_layers_keep_their_own_codes() -> None:
    downloader = OsmDownloader(httpx.AsyncClient(), [ROADS, PARKS])
    assert downloader.layers == ("roads", "parks")


async def test_all_layers_share_one_request() -> None:
    seen: list[httpx.Request] = []
    downloader = downloader_answering({"elements": []}, seen)
    await downloader.fetch(BOUNDS)

    assert len(seen) == 1
    query = seen[0].content.decode()
    assert "highway" in query
    assert "leisure" in query


@pytest.mark.db
async def test_store_keeps_elements_as_fetched(
    admin_conn: AsyncConnection[TupleRow], downloader_pool: Pool
) -> None:
    body = json.loads((FIXTURES / "overpass_roads_parks.json").read_text())
    downloader = downloader_answering(body, [])
    data = await downloader.fetch(BOUNDS)
    for _ in range(2):
        async with downloader_pool.connection() as conn:
            await downloader.store(conn, data)

    nodes = await admin_conn.execute(
        "SELECT id, tags, ST_X(geom), ST_Y(geom) FROM raw.osm_nodes ORDER BY id"
    )
    assert (await nodes.fetchall())[:2] == [
        (1, {}, 18.06, 59.33),
        (2, {"highway": "crossing"}, 18.061, 59.33),
    ]
    ways = await admin_conn.execute("SELECT id, tags, node_ids FROM raw.osm_ways ORDER BY id")
    assert await ways.fetchall() == [
        (10, {"highway": "footway"}, [1, 2, 5]),
        (11, {"highway": "residential", "name": "Parkgatan"}, [2, 3]),
        (20, {}, [1, 2, 3]),
        (21, {}, [3, 4, 1]),
    ]
    relations = await admin_conn.execute("SELECT id, tags->>'name', members FROM raw.osm_relations")
    assert await relations.fetchall() == [
        (
            30,
            "Small park",
            [
                {"type": "way", "ref": 20, "role": "outer"},
                {"type": "way", "ref": 21, "role": "outer"},
                {"type": "node", "ref": 5, "role": "label"},
            ],
        )
    ]


@pytest.mark.db
async def test_store_updates_moved_nodes_and_changed_ways(
    admin_conn: AsyncConnection[TupleRow], downloader_pool: Pool
) -> None:
    downloader = OsmDownloader(httpx.AsyncClient(), [ROADS])
    before = OsmData(
        nodes=[OsmNode(id=1, tags={}, lon=18.0, lat=59.0)],
        ways=[OsmWay(id=10, tags={"highway": "path"}, node_ids=[1, 2])],
        relations=[],
    )
    after = OsmData(
        nodes=[OsmNode(id=1, tags={}, lon=18.5, lat=59.5)],
        ways=[OsmWay(id=10, tags={"highway": "footway"}, node_ids=[1, 3, 2])],
        relations=[],
    )
    for data in (before, after):
        async with downloader_pool.connection() as conn:
            await downloader.store(conn, data)

    node = await admin_conn.execute("SELECT ST_X(geom), ST_Y(geom) FROM raw.osm_nodes")
    assert await node.fetchall() == [(18.5, 59.5)]
    way = await admin_conn.execute("SELECT tags->>'highway', node_ids FROM raw.osm_ways")
    assert await way.fetchall() == [("footway", [1, 3, 2])]


@pytest.mark.db
async def test_empty_payload_stores_nothing(
    admin_conn: AsyncConnection[TupleRow], downloader_pool: Pool
) -> None:
    downloader = OsmDownloader(httpx.AsyncClient(), [ROADS])
    async with downloader_pool.connection() as conn:
        await downloader.store(conn, OsmData(nodes=[], ways=[], relations=[]))

    cur = await admin_conn.execute(
        "SELECT (SELECT count(*) FROM raw.osm_nodes) + (SELECT count(*) FROM raw.osm_ways)"
        " + (SELECT count(*) FROM raw.osm_relations)"
    )
    assert await cur.fetchone() == (0,)
