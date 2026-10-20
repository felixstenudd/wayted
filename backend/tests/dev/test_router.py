import httpx
import pytest
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool
from starlette.types import Message, Receive, Scope, Send

from app.dev.main import app
from app.enrichment import enrich_pending
from app.graph import map_pending
from app.sources import queue
from app.sources.registry import mark_fetched
from app.sources.tiles import Tile

from ..enrichment.area_data import add_square
from ..graph.raw_data import add_line

pytestmark = pytest.mark.db

type Conn = AsyncConnection[TupleRow]
type Pool = AsyncConnectionPool[Conn]

TILE = Tile(x=8800, y=4700, z=14)
STOCKHOLM = {"lat": 59.33, "lon": 18.07}
# Around the grid raw_data draws on.
GRID = {"west": 17.99, "south": 59.29, "east": 18.01, "north": 59.31}


async def test_health(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")

    assert (response.status_code, response.json()) == (200, {"status": "ok"})


async def test_fetched_tiles_are_polygons_with_their_times(
    client: httpx.AsyncClient, downloader_pool: Pool
) -> None:
    async with downloader_pool.connection() as conn:
        await mark_fetched(conn, "roads", {TILE})

    response = await client.get("/tiles/fetched")

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "FeatureCollection"
    [feature] = body["features"]
    assert feature["type"] == "Feature"
    b = TILE.bounds
    assert feature["geometry"] == {
        "type": "Polygon",
        "coordinates": [
            [
                [b.west, b.south],
                [b.east, b.south],
                [b.east, b.north],
                [b.west, b.north],
                [b.west, b.south],
            ]
        ],
    }
    properties = feature["properties"]
    assert (properties["layer"], properties["z"], properties["x"], properties["y"]) == (
        "roads",
        14,
        8800,
        4700,
    )
    assert properties["fetched_at"] < properties["expires_at"]


async def test_queued_tiles_show_why_one_failed(
    client: httpx.AsyncClient, admin_conn: Conn, api_pool: Pool
) -> None:
    async with api_pool.connection() as conn:
        await queue.request_area(conn, TILE.bounds, layers=("roads", "parks"))
    await admin_conn.execute(
        """
        UPDATE raw.pending_tiles
        SET status = 'failed', attempts = 10, last_status = 'timeout', last_message = 'too slow'
        WHERE layer = 'roads'
        """
    )

    response = await client.get("/tiles/queued")

    assert response.status_code == 200
    by_layer = {f["properties"]["layer"]: f for f in response.json()["features"]}
    assert set(by_layer) == {"roads", "parks"}
    assert by_layer["roads"]["geometry"]["type"] == "Polygon"
    failed = by_layer["roads"]["properties"]
    assert (
        failed["status"],
        failed["attempts"],
        failed["last_status"],
        failed["last_message"],
    ) == (
        "failed",
        10,
        "timeout",
        "too slow",
    )
    waiting = by_layer["parks"]["properties"]
    assert (waiting["status"], waiting["attempts"], waiting["last_status"]) == ("pending", 0, None)
    assert waiting["requested_at"] <= waiting["next_attempt_at"]


async def test_graph_returns_edges_and_their_vertices(
    client: httpx.AsyncClient, admin_conn: Conn, mapper_pool: Pool
) -> None:
    await add_line(
        admin_conn, 10, [(1, 0, 0), (2, 2, 0)], {"highway": "residential", "name": "Main"}
    )
    await map_pending(mapper_pool.connection)

    response = await client.get("/graph", params=GRID)

    assert response.status_code == 200
    body = response.json()
    [edge] = body["edges"]["features"]
    assert edge["geometry"] == {"type": "LineString", "coordinates": [[18.0, 59.3], [18.002, 59.3]]}
    properties = edge["properties"]
    assert (properties["way_id"], properties["source"], properties["target"]) == (10, 1, 2)
    assert properties["tags"] == {"highway": "residential", "name": "Main"}
    assert properties["forward"] == ["cycling", "running"]
    assert properties["scores"] == {}
    assert properties["length_m"] == pytest.approx(113.7, abs=0.5)
    assert [(v["properties"]["id"], v["geometry"]) for v in body["vertices"]["features"]] == [
        (1, {"type": "Point", "coordinates": [18.0, 59.3]}),
        (2, {"type": "Point", "coordinates": [18.002, 59.3]}),
    ]


async def test_graph_of_an_empty_area_is_two_empty_collections(client: httpx.AsyncClient) -> None:
    response = await client.get("/graph", params=GRID)

    assert response.status_code == 200
    assert response.json() == {
        "edges": {"type": "FeatureCollection", "features": []},
        "vertices": {"type": "FeatureCollection", "features": []},
    }


async def test_graph_with_too_many_edges_says_to_zoom_in(
    client: httpx.AsyncClient,
    admin_conn: Conn,
    mapper_pool: Pool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await add_line(admin_conn, 10, [(1, 0, 0), (2, 2, 0), (3, 4, 0)], {"highway": "residential"})
    await add_line(admin_conn, 11, [(2, 2, 0), (4, 2, 2)], {"highway": "footway"})
    await map_pending(mapper_pool.connection)
    monkeypatch.setattr("app.dev.router.MAX_EDGES", 2)

    response = await client.get("/graph", params=GRID)

    assert response.status_code == 400
    assert response.json() == {"detail": "The area holds more than 2 edges. Zoom in and try again."}


@pytest.mark.parametrize(
    ("changed", "message"),
    [
        ({"west": 18.02}, "West must not be east of east."),
        ({"south": 59.32}, "South must not be north of north."),
    ],
)
async def test_graph_refuses_an_inside_out_box(
    client: httpx.AsyncClient, changed: dict[str, float], message: str
) -> None:
    response = await client.get("/graph", params={**GRID, **changed})

    assert (response.status_code, response.json()) == (400, {"detail": message})


@pytest.mark.parametrize(
    "params",
    [
        {"west": 17.99, "south": 59.29, "east": 18.01},
        {**GRID, "west": "left"},
        {**GRID, "east": 181},
        {**GRID, "north": 91},
    ],
)
async def test_graph_refuses_a_missing_or_impossible_side(
    client: httpx.AsyncClient, params: dict[str, float | str]
) -> None:
    response = await client.get("/graph", params=params)

    assert response.status_code == 422


def test_graph_documents_its_one_sentence_errors() -> None:
    spec = app.openapi()

    refused = spec["paths"]["/graph"]["get"]["responses"]["400"]
    schema = refused["content"]["application/json"]["schema"]
    assert schema == {"$ref": "#/components/schemas/ErrorOut"}
    assert spec["components"]["schemas"]["ErrorOut"]["properties"]["detail"]["type"] == "string"


async def test_areas_returns_the_parks_in_the_box(
    client: httpx.AsyncClient, admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square(admin_conn, 101, 1, (0, 0, 2, 2), {"leisure": "park", "name": "Square"})
    await map_pending(mapper_pool.connection)
    await enrich_pending(enricher_pool.connection)

    response = await client.get("/areas", params=GRID)

    assert response.status_code == 200
    [area] = response.json()["features"]
    corners = [[18.0, 59.3], [18.002, 59.3], [18.002, 59.302], [18.0, 59.302], [18.0, 59.3]]
    assert area["geometry"]["type"] == "MultiPolygon"
    [[ring]] = area["geometry"]["coordinates"]
    assert sorted(map(tuple, ring[:-1])) == sorted(map(tuple, corners[:-1]))
    assert area["properties"] == {
        "layer": "parks",
        "osm_type": "way",
        "osm_id": 101,
        "tags": {"leisure": "park", "name": "Square"},
    }


async def test_areas_outside_the_box_are_left_out(
    client: httpx.AsyncClient, admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square(admin_conn, 101, 1, (0, 0, 2, 2), {"leisure": "park"})
    await map_pending(mapper_pool.connection)
    await enrich_pending(enricher_pool.connection)

    response = await client.get("/areas", params={**GRID, "west": 18.005})

    assert response.json() == {"type": "FeatureCollection", "features": []}


async def test_areas_refuses_an_inside_out_box(client: httpx.AsyncClient) -> None:
    response = await client.get("/areas", params={**GRID, "west": 18.02})

    assert (response.status_code, response.json()) == (
        400,
        {"detail": "West must not be east of east."},
    )


async def test_lines_returns_the_rivers_in_the_box(
    client: httpx.AsyncClient, admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    river = {"waterway": "river", "name": "Älven"}
    await add_line(admin_conn, 101, [(1, 0, 0), (2, 2, 1)], river)
    await map_pending(mapper_pool.connection)
    await enrich_pending(enricher_pool.connection)

    response = await client.get("/lines", params=GRID)

    assert response.status_code == 200
    [line] = response.json()["features"]
    assert line["geometry"] == {
        "type": "MultiLineString",
        "coordinates": [[[18.0, 59.3], [18.002, 59.301]]],
    }
    assert line["properties"] == {
        "layer": "water_lines",
        "osm_type": "way",
        "osm_id": 101,
        "tags": river,
    }


async def test_lines_outside_the_box_are_left_out(
    client: httpx.AsyncClient, admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_line(admin_conn, 101, [(1, 0, 0), (2, 2, 1)], {"waterway": "river"})
    await map_pending(mapper_pool.connection)
    await enrich_pending(enricher_pool.connection)

    response = await client.get("/lines", params={**GRID, "west": 18.005})

    assert response.json() == {"type": "FeatureCollection", "features": []}


async def test_lines_refuses_an_inside_out_box(client: httpx.AsyncClient) -> None:
    response = await client.get("/lines", params={**GRID, "west": 18.02})

    assert (response.status_code, response.json()) == (
        400,
        {"detail": "West must not be east of east."},
    )


async def test_pending_counts_the_work_each_step_has_left(
    client: httpx.AsyncClient, admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_line(admin_conn, 10, [(1, 0, 0), (2, 2, 0)], {"highway": "path"})
    # Queued twice, counted once.
    await add_line(admin_conn, 10, [(1, 0, 0), (2, 2, 0)], {"highway": "path", "name": "P"})
    await map_pending(mapper_pool.connection)

    mapped = (await client.get("/pending")).json()
    await enrich_pending(enricher_pool.connection)
    enriched = (await client.get("/pending")).json()

    assert mapped == {
        "mapper": {"ways": 0, "nodes": 0},
        "enricher": {"ways": 1, "relations": 0, "nodes": 0, "edges": 1},
    }
    assert enriched == {
        "mapper": {"ways": 0, "nodes": 0},
        "enricher": {"ways": 0, "relations": 0, "nodes": 0, "edges": 0},
    }


async def test_pending_counts_ways_waiting_for_the_mapper(
    client: httpx.AsyncClient, admin_conn: Conn
) -> None:
    await add_line(admin_conn, 10, [(1, 0, 0), (2, 2, 0)], {"highway": "path"})

    response = await client.get("/pending")

    assert response.json()["mapper"]["ways"] == 1


async def test_request_queues_the_tiles_around_the_circle(
    client: httpx.AsyncClient, admin_conn: Conn
) -> None:
    response = await client.post("/requests", json={**STOCKHOLM, "radius_m": 2000})

    assert response.status_code == 202
    body = response.json()
    bounds = body["bounds"]
    assert bounds["west"] < 18.07 < bounds["east"]
    assert bounds["south"] < 59.33 < bounds["north"]
    assert bounds["north"] - bounds["south"] == pytest.approx(2 * 2000 / 111_195, rel=1e-4)
    cur = await admin_conn.execute(
        "SELECT layer, count(*), bool_and(status = 'pending') FROM raw.pending_tiles GROUP BY layer"
    )
    per_layer = {layer: (count, pending) for layer, count, pending in await cur.fetchall()}
    # Every layer covers the same tiles, all waiting.
    [(count, pending)] = set(per_layer.values())
    assert pending
    assert body["queued_by_layer"] == {layer: count for layer in queue.LAYER_CODES}
    assert body["queued"] == len(queue.LAYER_CODES) * count


async def test_request_is_committed_before_the_answer_is_sent(
    client: httpx.AsyncClient, admin_conn: Conn
) -> None:
    visible: list[int] = []

    async def counting(scope: Scope, receive: Receive, send: Send) -> None:
        async def send_counted(message: Message) -> None:
            if message["type"] == "http.response.start":
                cur = await admin_conn.execute("SELECT count(*) FROM raw.pending_tiles")
                row = await cur.fetchone()
                assert row is not None
                visible.append(row[0])
            await send(message)

        await app(scope, receive, send_counted)

    transport = httpx.ASGITransport(app=counting)
    async with httpx.AsyncClient(transport=transport, base_url="http://dev") as http:
        response = await http.post("/requests", json={**STOCKHOLM, "radius_m": 1})

    assert visible == [response.json()["queued"]] == [len(queue.LAYER_CODES)]


async def test_request_for_tiles_already_waiting_queues_nothing(client: httpx.AsyncClient) -> None:
    await client.post("/requests", json={**STOCKHOLM, "radius_m": 2000})

    response = await client.post("/requests", json={**STOCKHOLM, "radius_m": 2000})

    assert (response.status_code, response.json()["queued"]) == (202, 0)


async def test_refetch_queues_tiles_that_are_fetched(
    client: httpx.AsyncClient, downloader_pool: Pool
) -> None:
    tile = Tile.from_lat_lon(59.33, 18.07, 14)
    async with downloader_pool.connection() as conn:
        for layer in queue.LAYER_CODES:
            await mark_fetched(conn, layer, {tile})

    plain = await client.post("/requests", json={**STOCKHOLM, "radius_m": 1})
    refetch = await client.post("/requests", json={**STOCKHOLM, "radius_m": 1, "refetch": True})

    assert plain.json()["queued_by_layer"] == {layer: 0 for layer in queue.LAYER_CODES}
    assert refetch.json()["queued_by_layer"] == {layer: 1 for layer in queue.LAYER_CODES}


async def test_request_at_the_radius_limit_is_accepted(client: httpx.AsyncClient) -> None:
    response = await client.post("/requests", json={**STOCKHOLM, "radius_m": 40_000})

    assert response.status_code == 202
    assert response.json()["queued"] > 8000


@pytest.mark.parametrize(
    "body",
    [
        {**STOCKHOLM, "radius_m": 40_001},
        {**STOCKHOLM, "radius_m": 0},
        {**STOCKHOLM, "radius_m": -5},
        {"lat": 86, "lon": 18.07, "radius_m": 1000},
        {"lat": 59.33, "lon": 181, "radius_m": 1000},
        {"lat": 59.33, "lon": 18.07},
        {"lat": "north", "lon": 18.07, "radius_m": 1000},
    ],
)
async def test_request_refuses_a_bad_circle(
    client: httpx.AsyncClient, admin_conn: Conn, body: dict[str, object]
) -> None:
    response = await client.post("/requests", json=body)

    assert response.status_code == 422
    cur = await admin_conn.execute("SELECT count(*) FROM raw.pending_tiles")
    assert await cur.fetchone() == (0,)
