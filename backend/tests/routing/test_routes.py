from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from psycopg import AsyncConnection
from psycopg.rows import TupleRow

from app.auth.dependencies import current_user
from app.dependencies import api_conn
from app.graph import map_pending
from app.routing import service
from app.routing.router import router
from app.sources.queue import LAYER_CODES
from app.sources.registry import mark_fetched
from app.sources.tiles import Tile, tiles_for_bounds

from ..graph.raw_data import ORIGIN_LAT, ORIGIN_LON, STEP, Conn
from .network_data import COLUMN_STEPS, add_grid, node_id
from .test_planner import Pool

pytestmark = pytest.mark.db

ZOOM = 14
CENTRE = {"lon": ORIGIN_LON + 12 * COLUMN_STEPS * STEP, "lat": ORIGIN_LAT + 12 * STEP}
LOOP: dict[str, Any] = {
    "activity": "running",
    "shape": "loop",
    "start": CENTRE,
    "target_distance_m": 2_000,
    # water is not scored yet and is dropped.
    "preferences": {"green": 0.5, "water": 1},
}
QUERY = service.RouteQuery(
    activity="running",
    start=service.Coordinate(**CENTRE),
    finish=None,
    target_m=2_000,
    weights={},
)


@pytest.fixture
async def client(api_pool: Pool) -> AsyncIterator[httpx.AsyncClient]:
    """The routing router with a signed-in user, its connections from the wayted_api pool."""

    async def test_conn() -> AsyncIterator[AsyncConnection[TupleRow]]:
        async with api_pool.connection() as conn:
            yield conn

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[current_user] = uuid4
    app.dependency_overrides[api_conn] = test_conn
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://api") as http:
        yield http


async def fetched(conn: Conn, api_pool: Pool) -> None:
    """Mark every tile the loop needs as fetched, as the worker does once it is in the graph."""
    async with api_pool.connection() as api:
        bounds = await service.search_bounds(api, QUERY)
    for layer in LAYER_CODES:
        await mark_fetched(conn, layer, tiles_for_bounds(bounds, ZOOM))


async def mapped_grid(conn: Conn, mapper_pool: Pool, api_pool: Pool) -> None:
    await add_grid(conn, {"highway": "residential"})
    await map_pending(mapper_pool.connection)
    # The mapper queues every new edge for the enricher; these tests have nothing to score.
    await conn.execute("TRUNCATE graph.pending_edges")
    await fetched(conn, api_pool)


async def test_new_area_is_queued_and_the_client_asked_to_wait(
    admin_conn: Conn, client: httpx.AsyncClient
) -> None:
    res = await client.post("/routing/routes", json=LOOP)

    assert res.status_code == 202
    assert res.json() == {"status": "preparing"}
    cur = await admin_conn.execute("SELECT DISTINCT layer FROM raw.pending_tiles ORDER BY layer")
    assert [layer for (layer,) in await cur.fetchall()] == sorted(LAYER_CODES)


async def test_area_in_the_graph_gets_a_route(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool, client: httpx.AsyncClient
) -> None:
    await mapped_grid(admin_conn, mapper_pool, api_pool)

    res = await client.post("/routing/routes", json=LOOP)

    assert res.status_code == 200
    route = res.json()
    assert route["type"] == "Feature"
    assert route["geometry"]["type"] == "LineString"
    assert route["geometry"]["coordinates"][0] == route["geometry"]["coordinates"][-1]
    properties = route["properties"]
    assert properties["length_m"] == pytest.approx(2_000, rel=0.07)
    assert properties["warnings"] == []
    assert properties["reused_m"] >= 0
    cur = await admin_conn.execute("SELECT count(*) FROM raw.pending_tiles")
    assert await cur.fetchone() == (0,)


async def test_route_to_a_finish_needs_no_target(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool, client: httpx.AsyncClient
) -> None:
    await mapped_grid(admin_conn, mapper_pool, api_pool)
    finish = {"lon": CENTRE["lon"] + 4 * COLUMN_STEPS * STEP, "lat": CENTRE["lat"]}
    request = {**LOOP, "shape": "point_to_point", "finish": finish}
    del request["target_distance_m"]

    res = await client.post("/routing/routes", json=request)

    assert res.status_code == 200
    properties = res.json()["properties"]
    # Four blocks east.
    assert properties["length_m"] == pytest.approx(4 * 113.7, rel=0.01)
    assert properties["warnings"] == []


async def test_tile_still_being_fetched_keeps_the_client_waiting(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool, client: httpx.AsyncClient
) -> None:
    await mapped_grid(admin_conn, mapper_pool, api_pool)
    await admin_conn.execute("DELETE FROM raw.fetched_tiles WHERE layer = 'parks'")

    first = await client.post("/routing/routes", json=LOOP)
    await admin_conn.execute("UPDATE raw.pending_tiles SET status = 'running'")
    second = await client.post("/routing/routes", json=LOOP)

    assert (first.status_code, second.status_code) == (202, 202)


async def test_edges_waiting_for_scores_keep_the_client_waiting(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool, client: httpx.AsyncClient
) -> None:
    await mapped_grid(admin_conn, mapper_pool, api_pool)
    await admin_conn.execute(
        "INSERT INTO graph.pending_edges (edge_id) SELECT id FROM graph.edges WHERE source = %s",
        (node_id(12, 12),),
    )

    res = await client.post("/routing/routes", json=LOOP)

    assert res.status_code == 202


async def test_heights_waiting_for_the_enricher_keep_the_client_waiting(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool, client: httpx.AsyncClient
) -> None:
    await mapped_grid(admin_conn, mapper_pool, api_pool)
    tile = Tile.from_lat_lon(CENTRE["lat"], CENTRE["lon"], ZOOM)
    await admin_conn.execute(
        "INSERT INTO enrich.pending_elevation (z, x, y) VALUES (%s, %s, %s)",
        (tile.z, tile.x, tile.y),
    )

    res = await client.post("/routing/routes", json=LOOP)

    assert res.status_code == 202


async def test_start_far_from_any_road_has_no_route(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool, client: httpx.AsyncClient
) -> None:
    await mapped_grid(admin_conn, mapper_pool, api_pool)
    # Inside the fetched tiles, 600 m north of the grid.
    start = {"lon": CENTRE["lon"], "lat": ORIGIN_LAT + 30 * STEP}
    async with api_pool.connection() as api:
        bounds = await service.search_bounds(
            api, service.RouteQuery("running", service.Coordinate(**start), None, 2_000, {})
        )
    for layer in LAYER_CODES:
        await mark_fetched(admin_conn, layer, tiles_for_bounds(bounds, ZOOM))

    res = await client.post("/routing/routes", json={**LOOP, "start": start})

    assert res.status_code == 422
    assert res.json() == {"detail": "start_off_road"}


async def test_weights_for_unscored_attributes_are_dropped(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    await mapped_grid(admin_conn, mapper_pool, api_pool)
    unscored = service.RouteQuery("running", QUERY.start, None, 2_000, {"water": 1})

    async with api_pool.connection() as conn:
        with_unscored = await service.plan(conn, unscored)
        without = await service.plan(conn, QUERY)

    assert with_unscored == without
