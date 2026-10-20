import asyncio
import json
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from app.sources.osm import (
    NATURE,
    PARKS,
    ROADS,
    WATER,
    WATER_LINES,
    OsmData,
    OsmDownloader,
    OsmNode,
    OsmWay,
)
from app.sources.osm.layers import area_selectors
from app.sources.osm.overpass import build_query
from app.sources.tiles import Bounds

FIXTURES = Path(__file__).parents[2] / "fixtures"
Pool = AsyncConnectionPool[AsyncConnection[TupleRow]]
BOUNDS = Bounds(west=18.0, south=59.0, east=18.1, north=59.1)


def client_answering(body: object, seen: list[httpx.Request]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def sent_query(request: httpx.Request) -> str:
    return parse_qs(request.content.decode())["data"][0]


async def test_layers_keep_their_own_codes() -> None:
    async with httpx.AsyncClient() as client:
        assert OsmDownloader(client, [ROADS, PARKS]).layers == ("roads", "parks")


async def test_all_layers_share_one_request() -> None:
    seen: list[httpx.Request] = []
    async with client_answering({"elements": []}, seen) as client:
        await OsmDownloader(client, [ROADS, PARKS]).fetch(BOUNDS)

    assert len(seen) == 1
    assert sent_query(seen[0]) == build_query(
        ROADS.selectors + PARKS.selectors,
        BOUNDS,
        enclosing_selectors=PARKS.selectors,
        shallow_selectors=ROADS.shallow_selectors,
    )


async def test_layers_without_areas_skip_the_enclosing_lookup() -> None:
    seen: list[httpx.Request] = []
    async with client_answering({"elements": []}, seen) as client:
        await OsmDownloader(client, [ROADS]).fetch(BOUNDS)

    assert sent_query(seen[0]) == build_query(
        ROADS.selectors, BOUNDS, shallow_selectors=ROADS.shallow_selectors
    )
    assert "is_in" not in sent_query(seen[0])


async def test_roads_include_ferries_and_route_relations_without_members() -> None:
    seen: list[httpx.Request] = []
    async with client_answering({"elements": []}, seen) as client:
        await OsmDownloader(client, [ROADS]).fetch(BOUNDS)

    query = sent_query(seen[0])
    deep, shallow = query.split("->.deep;")
    assert 'way["route"="ferry"]' in deep
    assert 'relation["route"~"^(bicycle|foot|hiking|running|mtb)$"]' in shallow


async def test_nature_asks_for_each_kind_of_land_as_ways_and_multipolygons() -> None:
    seen: list[httpx.Request] = []
    async with client_answering({"elements": []}, seen) as client:
        await OsmDownloader(client, [NATURE]).fetch(BOUNDS)

    query = sent_query(seen[0])
    assert "is_in" in query
    for key, values in [
        ("landuse", "forest|meadow"),
        ("natural", "wood|scrub|heath|grassland|wetland"),
    ]:
        assert f'way["{key}"~"^({values})$"]' in query
        assert f'relation["{key}"~"^({values})$"]["type"="multipolygon"]' in query
    assert 'way["leisure"="nature_reserve"]' in query
    assert 'relation["leisure"="nature_reserve"]["type"="multipolygon"]' in query


async def test_water_asks_for_each_kind_as_ways_and_multipolygons() -> None:
    seen: list[httpx.Request] = []
    async with client_answering({"elements": []}, seen) as client:
        await OsmDownloader(client, [WATER]).fetch(BOUNDS)

    query = sent_query(seen[0])
    assert "is_in" in query
    for selector in [
        '["natural"="water"]',
        '["waterway"="riverbank"]',
        '["landuse"~"^(reservoir|basin)$"]',
    ]:
        assert f"way{selector}" in query
        assert f'relation{selector}["type"="multipolygon"]' in query


async def test_water_lines_ask_for_ways_only() -> None:
    seen: list[httpx.Request] = []
    async with client_answering({"elements": []}, seen) as client:
        await OsmDownloader(client, [WATER_LINES]).fetch(BOUNDS)

    query = sent_query(seen[0])
    assert 'way["natural"="coastline"]' in query
    assert 'way["waterway"~"^(river|canal)$"]' in query
    assert "relation" not in query
    assert "is_in" not in query


def test_area_selectors_merge_the_values_of_one_key() -> None:
    tags = (
        {"landuse": "forest"},
        {"natural": "wood"},
        {"landuse": "meadow"},
        {"leisure": "park", "access": "yes"},
    )

    assert area_selectors(tags) == (
        'way["landuse"~"^(forest|meadow)$"]',
        'way["natural"="wood"]',
        'way["leisure"="park"]["access"="yes"]',
        'relation["landuse"~"^(forest|meadow)$"]["type"="multipolygon"]',
        'relation["natural"="wood"]["type"="multipolygon"]',
        'relation["leisure"="park"]["access"="yes"]["type"="multipolygon"]',
    )


@pytest.mark.db
async def test_store_keeps_elements_as_fetched(
    admin_conn: AsyncConnection[TupleRow], downloader_pool: Pool
) -> None:
    body = json.loads((FIXTURES / "overpass_roads_parks.json").read_text())
    async with client_answering(body, []) as client:
        downloader = OsmDownloader(client, [ROADS, PARKS])
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
    async with httpx.AsyncClient() as client:
        downloader = OsmDownloader(client, [ROADS])
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
    async with httpx.AsyncClient() as client, downloader_pool.connection() as conn:
        await OsmDownloader(client, [ROADS]).store(conn, OsmData(nodes=[], ways=[], relations=[]))

    cur = await admin_conn.execute(
        "SELECT (SELECT count(*) FROM raw.osm_nodes) + (SELECT count(*) FROM raw.osm_ways)"
        " + (SELECT count(*) FROM raw.osm_relations)"
    )
    assert await cur.fetchone() == (0,)


@pytest.mark.db
async def test_storing_the_same_data_again_leaves_rows_untouched(
    admin_conn: AsyncConnection[TupleRow], downloader_pool: Pool
) -> None:
    body = json.loads((FIXTURES / "overpass_roads_parks.json").read_text())

    async def row_versions() -> list[tuple[str, int, str]]:
        cur = await admin_conn.execute(
            """
            SELECT 'node', id, xmin::text FROM raw.osm_nodes
            UNION ALL SELECT 'way', id, xmin::text FROM raw.osm_ways
            UNION ALL SELECT 'relation', id, xmin::text FROM raw.osm_relations
            ORDER BY 1, 2
            """
        )
        return await cur.fetchall()

    async with client_answering(body, []) as client:
        downloader = OsmDownloader(client, [ROADS, PARKS])
        data = await downloader.fetch(BOUNDS)
        async with downloader_pool.connection() as conn:
            await downloader.store(conn, data)
        before = await row_versions()
        async with downloader_pool.connection() as conn:
            await downloader.store(conn, data)

    assert await row_versions() == before


@pytest.mark.db
async def test_concurrent_stores_in_opposite_orders_do_not_deadlock(
    admin_conn: AsyncConnection[TupleRow], downloader_pool: Pool
) -> None:
    nodes = [OsmNode(id=i, tags={}, lon=18.0, lat=59.0) for i in range(1, 2001)]

    async def store(order: list[OsmNode]) -> None:
        async with httpx.AsyncClient() as client, downloader_pool.connection() as conn:
            await OsmDownloader(client, [ROADS]).store(conn, OsmData(order, [], []))

    for _ in range(3):
        await asyncio.gather(store(nodes), store(nodes[::-1]))
