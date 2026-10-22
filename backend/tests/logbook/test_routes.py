from typing import Any

import httpx
import pytest
from psycopg import AsyncConnection
from psycopg.rows import TupleRow

from app.main import app

from .app_data import add_edge, add_user

pytestmark = pytest.mark.db

type Conn = AsyncConnection[TupleRow]

V0 = (20.0, 63.8)
MID = (20.0005, 63.8005)
V1 = (20.001, 63.8)
V2 = (20.002, 63.8)
V3 = (20.002, 63.801)


async def add_network(conn: Conn) -> tuple[int, int, int]:
    """a: V0-MID-V1, 60 m. b: V1-V2, 40 m. c: V2-V3, 100 m, cyclists only from V2 to V3."""
    a = await add_edge(conn, 0, 1, [V0, MID, V1], length_m=60, scores={"green": 1.0})
    b = await add_edge(conn, 1, 2, [V1, V2], length_m=40, scores={"green": 0.5, "water": 0.2})
    c = await add_edge(conn, 2, 3, [V2, V3], length_m=100, backward=("running",))
    return a, b, c


async def add_other_users_route(conn: Conn) -> int:
    other = await add_user(conn, "other@example.com")
    cur = await conn.execute(
        """
        INSERT INTO app.routes
            (user_id, name, activity, shape, target_distance_m, geom, distance_m)
        VALUES (%s, 'Not yours', 'running', 'loop', 5000, %s, 60)
        RETURNING id
        """,
        (other, "SRID=4326;LINESTRING(20 63.8, 20.001 63.8)"),
    )
    row = await cur.fetchone()
    assert row is not None
    route_id: int = row[0]
    return route_id


def route(edges: list[tuple[int, bool]], **overrides: Any) -> dict[str, Any]:
    return {
        "name": "Morning loop",
        "activity": "running",
        "shape": "point_to_point",
        "target_distance_m": 5000,
        "preferences": {"green": 0.5},
        "edges": [{"edge_id": edge_id, "forward": forward} for edge_id, forward in edges],
    } | overrides


async def create(client: httpx.AsyncClient, body: dict[str, Any]) -> dict[str, Any]:
    response = await client.post("/logbook/routes", json=body)
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


def coords(geometry: dict[str, Any]) -> list[tuple[float, float]]:
    return [(round(lon, 6), round(lat, 6)) for lon, lat in geometry["coordinates"]]


async def test_saving_derives_the_line_distance_and_scores(
    client: httpx.AsyncClient, app_conn: Conn
) -> None:
    a, b, _ = await add_network(app_conn)

    saved = await create(client, route([(a, True), (b, True)]))

    assert coords(saved["geometry"]) == [V0, MID, V1, V2]
    assert saved["distance_m"] == 100
    assert saved["scores"] == {
        "green": {"mean": 0.8, "coverage": 1.0},
        "water": {"mean": 0.2, "coverage": 0.4},
    }
    assert saved["edges"] == [
        {"seq": 0, "length_m": 60, "last_point": 2},
        {"seq": 1, "length_m": 40, "last_point": 3},
    ]
    assert saved["preferences"] == {"green": 0.5}
    # No heights are known on these edges.
    assert (saved["ascent_m"], saved["descent_m"]) == (None, None)


async def test_saving_keeps_the_metres_climbed_and_dropped_as_they_were(
    client: httpx.AsyncClient, app_conn: Conn
) -> None:
    a, b, _ = await add_network(app_conn)
    await app_conn.execute("UPDATE graph.edges SET ascent_m = 5, descent_m = 1 WHERE id = %s", (a,))
    await app_conn.execute("UPDATE graph.edges SET ascent_m = 2, descent_m = 3 WHERE id = %s", (b,))

    # Travelled backwards, each edge climbs what it drops forwards.
    saved = await create(client, route([(b, False), (a, False)]))
    await app_conn.execute("UPDATE graph.edges SET ascent_m = 50, descent_m = 50")
    read = (await client.get(f"/logbook/routes/{saved['id']}")).json()

    assert (saved["ascent_m"], saved["descent_m"]) == (4, 7)
    assert (read["ascent_m"], read["descent_m"]) == (4, 7)


async def test_edges_run_backwards_when_not_forward(
    client: httpx.AsyncClient, app_conn: Conn
) -> None:
    a, b, _ = await add_network(app_conn)

    saved = await create(client, route([(b, False), (a, False)]))

    assert coords(saved["geometry"]) == [V2, V1, MID, V0]
    assert [e["last_point"] for e in saved["edges"]] == [1, 3]


@pytest.mark.parametrize(
    ("make_edges", "activity", "message"),
    [
        (lambda a, b, c: [(a, True), (999, True)], "running", "not in the map"),
        (lambda a, b, c: [(a, True), (c, True)], "running", "does not continue"),
        (lambda a, b, c: [(c, False)], "cycling", "cycling"),
    ],
    ids=["unknown edge", "gap", "not allowed"],
)
async def test_edge_lists_that_cannot_be_followed_are_refused(
    client: httpx.AsyncClient, app_conn: Conn, make_edges: Any, activity: str, message: str
) -> None:
    edges = make_edges(*await add_network(app_conn))

    response = await client.post("/logbook/routes", json=route(edges, activity=activity))

    assert response.status_code == 422
    assert message in response.json()["detail"]


async def test_a_way_to_a_finish_saves_without_a_target(
    client: httpx.AsyncClient, app_conn: Conn
) -> None:
    a, b, _ = await add_network(app_conn)
    body = route([(a, True), (b, True)])
    del body["target_distance_m"]

    saved = await create(client, body)

    assert saved["target_distance_m"] is None
    read = (await client.get(f"/logbook/routes/{saved['id']}")).json()
    assert read["target_distance_m"] is None


async def test_a_loop_still_needs_a_target(client: httpx.AsyncClient, app_conn: Conn) -> None:
    a, b, _ = await add_network(app_conn)
    body = route([(a, True), (b, True)], shape="loop")
    del body["target_distance_m"]

    response = await client.post("/logbook/routes", json=body)

    assert response.status_code == 422


async def test_through_points_are_kept_as_planned(
    client: httpx.AsyncClient, app_conn: Conn
) -> None:
    a, b, _ = await add_network(app_conn)
    waypoints = [
        {"lon": 20.0005, "lat": 63.8005, "at": "any", "after_m": None},
        {"lon": 20.002, "lat": 63.8, "at": "after", "after_m": 2_000},
    ]

    saved = await create(client, route([(a, True), (b, True)], waypoints=waypoints))

    assert saved["waypoints"] == waypoints
    plain = await create(client, route([(a, True), (b, True)]))
    assert plain["waypoints"] == []


async def test_a_through_point_after_needs_its_length(
    client: httpx.AsyncClient, app_conn: Conn
) -> None:
    a, b, _ = await add_network(app_conn)
    body = route([(a, True), (b, True)], waypoints=[{"lon": 20, "lat": 63.8, "at": "after"}])

    response = await client.post("/logbook/routes", json=body)

    assert response.status_code == 422


async def test_running_may_use_a_one_way_street_backwards(
    client: httpx.AsyncClient, app_conn: Conn
) -> None:
    _, _, c = await add_network(app_conn)

    saved = await create(client, route([(c, False)]))

    assert coords(saved["geometry"]) == [V3, V2]


async def test_unknown_attributes_in_preferences_are_refused(
    client: httpx.AsyncClient, app_conn: Conn
) -> None:
    a, _, _ = await add_network(app_conn)

    response = await client.post(
        "/logbook/routes", json=route([(a, True)], preferences={"lava": 1})
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "overrides",
    [{"name": "Morning\x00loop"}, {"edges": [{"edge_id": 2**63, "forward": True}]}],
    ids=["NUL in the name", "edge id past bigint"],
)
async def test_input_the_database_cannot_hold_is_refused(
    client: httpx.AsyncClient, app_conn: Conn, overrides: dict[str, Any]
) -> None:
    a, _, _ = await add_network(app_conn)

    response = await client.post("/logbook/routes", json=route([(a, True)]) | overrides)

    assert response.status_code == 422


async def test_the_list_has_only_your_routes_newest_first(
    client: httpx.AsyncClient, app_conn: Conn
) -> None:
    a, b, _ = await add_network(app_conn)
    await create(client, route([(a, True)], name="First"))
    await create(client, route([(a, True), (b, True)], name="Second"))
    await add_other_users_route(app_conn)

    response = await client.get("/logbook/routes")

    assert response.status_code == 200
    listed = response.json()
    assert [r["name"] for r in listed] == ["Second", "First"]
    assert listed[0]["geometry"]["type"] == "LineString"
    assert listed[0]["distance_m"] == 100


async def test_a_route_can_be_read_renamed_and_deleted(
    client: httpx.AsyncClient, app_conn: Conn
) -> None:
    a, _, _ = await add_network(app_conn)
    saved = await create(client, route([(a, True)]))
    path = f"/logbook/routes/{saved['id']}"

    assert (await client.get(path)).json() == saved

    renamed = await client.patch(path, json={"name": "  Evening loop "})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Evening loop"

    assert (await client.delete(path)).status_code == 204
    assert (await client.get(path)).status_code == 404


async def test_other_users_routes_are_not_found(client: httpx.AsyncClient, app_conn: Conn) -> None:
    path = f"/logbook/routes/{await add_other_users_route(app_conn)}"

    assert (await client.get(path)).status_code == 404
    assert (await client.patch(path, json={"name": "Mine now"})).status_code == 404
    assert (await client.delete(path)).status_code == 404


async def test_routes_need_a_signed_in_user() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://api") as http:
        response = await http.get("/logbook/routes")

    assert response.status_code == 401
