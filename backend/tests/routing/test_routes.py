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
    # bridges are not scored yet and are dropped.
    "preferences": {"green": 0.5, "bridges": 1},
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
    found = res.json()
    assert found["type"] == "FeatureCollection"
    # The best first, then the options.
    assert 1 <= len(found["features"]) <= 3
    route = found["features"][0]
    assert route["type"] == "Feature"
    assert route["geometry"]["type"] == "LineString"
    assert route["geometry"]["coordinates"][0] == route["geometry"]["coordinates"][-1]
    properties = route["properties"]
    assert properties["length_m"] == pytest.approx(2_000, rel=0.07)
    assert properties["warnings"] == []
    assert properties["reused_m"] >= 0
    # The grid has nothing to score, so there is nothing known about any attribute or height.
    assert properties["scores"] == {}
    assert (properties["ascent_m"], properties["descent_m"]) == (None, None)
    steps = properties["edges"]
    assert steps and all(set(step) == {"edge_id", "forward"} for step in steps)
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
    properties = res.json()["features"][0]["properties"]
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
    unscored = service.RouteQuery("running", QUERY.start, None, 2_000, {"bridges": 1})

    async with api_pool.connection() as conn:
        with_unscored = await service.plan(conn, unscored)
        without = await service.plan(conn, QUERY)

    assert with_unscored == without


def grid_spot(column: float, row: float, **place: object) -> dict[str, Any]:
    return {
        "lon": ORIGIN_LON + column * COLUMN_STEPS * STEP,
        "lat": ORIGIN_LAT + row * STEP,
        **place,
    }


async def test_route_passes_its_waypoints_and_says_in_which_order(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool, client: httpx.AsyncClient
) -> None:
    await mapped_grid(admin_conn, mapper_pool, api_pool)
    request = {**LOOP, "waypoints": [grid_spot(10, 12), grid_spot(13, 13, at="asap")]}

    res = await client.post("/routing/routes", json=request)

    assert res.status_code == 200
    assert res.json()["features"][0]["properties"]["waypoint_order"] == [1, 0]


async def test_waypoints_widen_the_area_that_is_prepared(api_pool: Pool) -> None:
    far = service.Coordinate(lon=CENTRE["lon"] + 0.05, lat=CENTRE["lat"])
    with_far = service.RouteQuery(
        "running", QUERY.start, None, 2_000, {}, (service.Waypoint(far, "any", None),)
    )

    async with api_pool.connection() as conn:
        plain = await service.search_bounds(conn, QUERY)
        widened = await service.search_bounds(conn, with_far)

    assert widened.east > far.lon > plain.east


async def test_waypoint_far_from_any_road_has_no_route(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool, client: httpx.AsyncClient
) -> None:
    await mapped_grid(admin_conn, mapper_pool, api_pool)
    # 600 m north of the grid, in tiles that have been fetched.
    spot = grid_spot(12, 30)
    off_road = service.Waypoint(service.Coordinate(spot["lon"], spot["lat"]), "any", None)
    async with api_pool.connection() as api:
        bounds = await service.search_bounds(
            api, service.RouteQuery("running", QUERY.start, None, 2_000, {}, (off_road,))
        )
    for layer in LAYER_CODES:
        await mark_fetched(admin_conn, layer, tiles_for_bounds(bounds, ZOOM))
    request = {**LOOP, "waypoints": [spot]}

    res = await client.post("/routing/routes", json=request)

    assert res.status_code == 422
    assert res.json() == {"detail": "waypoint_off_road"}


@pytest.mark.parametrize(
    "waypoint",
    [
        grid_spot(12, 14, at="after"),
        grid_spot(12, 14, at="any", after_m=500),
        grid_spot(12, 14, at="after", after_m=0),
        grid_spot(12, 14, at="soon"),
        {"lon": 200, "lat": 63},
    ],
)
async def test_bad_waypoints_are_refused(client: httpx.AsyncClient, waypoint: object) -> None:
    res = await client.post("/routing/routes", json={**LOOP, "waypoints": [waypoint]})

    assert res.status_code == 422


async def test_edit_moves_the_route_onto_the_road_it_was_dropped_on(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool, client: httpx.AsyncClient
) -> None:
    await mapped_grid(admin_conn, mapper_pool, api_pool)
    found = await client.post("/routing/routes", json=LOOP)
    route = found.json()["features"][0]
    on_route = route["geometry"]["coordinates"][len(route["geometry"]["coordinates"]) // 2]

    res = await client.post(
        "/routing/routes/reroute",
        json={
            "activity": "running",
            "edges": route["properties"]["edges"],
            "grab": {"lon": on_route[0], "lat": on_route[1]},
            "drop": {"lon": on_route[0] + 2 * COLUMN_STEPS * STEP, "lat": on_route[1]},
            "target_distance_m": 2_000,
        },
    )

    assert res.status_code == 200
    body = res.json()
    assert body["route"]["type"] == "Feature"
    assert body["route"]["properties"]["edges"] != route["properties"]["edges"]
    assert body["handle"]["type"] == "Point"


async def test_edit_dropped_far_from_any_road_has_no_route(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool, client: httpx.AsyncClient
) -> None:
    await mapped_grid(admin_conn, mapper_pool, api_pool)
    route = (await client.post("/routing/routes", json=LOOP)).json()["features"][0]

    res = await client.post(
        "/routing/routes/reroute",
        json={
            "activity": "running",
            "edges": route["properties"]["edges"],
            "grab": CENTRE,
            "drop": {"lon": CENTRE["lon"], "lat": ORIGIN_LAT + 40 * STEP},
        },
    )

    assert res.status_code == 422
    assert res.json() == {"detail": "drop_off_road"}


async def test_edit_of_edges_that_do_not_join_up_is_refused(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool, client: httpx.AsyncClient
) -> None:
    await mapped_grid(admin_conn, mapper_pool, api_pool)
    route = (await client.post("/routing/routes", json=LOOP)).json()["features"][0]
    edges = route["properties"]["edges"]

    res = await client.post(
        "/routing/routes/reroute",
        json={"activity": "running", "edges": edges[:2] + edges[4:], "grab": CENTRE, "drop": None},
    )

    assert res.status_code == 422
    # Edges stop joining up when the map is built again under a route found earlier.
    assert res.json() == {"detail": "route_changed"}
