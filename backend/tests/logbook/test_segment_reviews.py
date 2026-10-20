from typing import Any

import httpx
import pytest
from psycopg import AsyncConnection
from psycopg.rows import TupleRow

from .app_data import add_edges, add_user

pytestmark = pytest.mark.db

type Conn = AsyncConnection[TupleRow]


async def saved_route(client: httpx.AsyncClient, steps: list[tuple[int, bool]]) -> int:
    response = await client.post(
        "/logbook/routes",
        json={
            "name": "Morning loop",
            "activity": "running",
            "shape": "loop",
            "target_distance_m": 5000,
            "edges": [{"edge_id": edge_id, "forward": forward} for edge_id, forward in steps],
        },
    )
    assert response.status_code == 201, response.text
    route_id: int = response.json()["id"]
    return route_id


async def review_stretch(
    client: httpx.AsyncClient, route_id: int, body: dict[str, Any]
) -> httpx.Response:
    return await client.post(f"/logbook/routes/{route_id}/segment-reviews", json=body)


async def reviewed_edges(conn: Conn, review_id: int) -> set[int]:
    cur = await conn.execute(
        "SELECT edge_id FROM app.segment_review_edges WHERE review_id = %s", (review_id,)
    )
    return {row[0] for row in await cur.fetchall()}


def coords(geometry: dict[str, Any]) -> list[tuple[float, float]]:
    return [(round(lon, 6), round(lat, 6)) for lon, lat in geometry["coordinates"]]


async def test_the_reasons_say_their_topic_and_side(client: httpx.AsyncClient) -> None:
    response = await client.get("/logbook/review-reasons")

    assert response.status_code == 200
    reasons = {r["code"]: r for r in response.json()}
    assert reasons["green_bad"] == {
        "code": "green_bad",
        "topic": "green",
        "sentiment": -1,
        "attribute": "green",
    }
    assert reasons["access_bad"]["attribute"] is None


async def test_a_stretch_review_covers_the_chosen_edges_of_the_route(
    client: httpx.AsyncClient, app_conn: Conn
) -> None:
    edges = await add_edges(app_conn, 3)
    route_id = await saved_route(client, [(edge, True) for edge in edges])

    response = await review_stretch(
        client,
        route_id,
        {
            "from_seq": 1,
            "to_seq": 2,
            "reasons": ["water_good", "prepared_bad"],
            "comment": "Gravel",
        },
    )

    assert response.status_code == 201, response.text
    review = response.json()
    assert coords(review["geometry"]) == [(20.001, 63.8), (20.002, 63.8), (20.003, 63.8)]
    assert (review["route_id"], review["from_seq"], review["to_seq"]) == (route_id, 1, 2)
    assert review["activity"] == "running"
    assert review["reasons"] == ["prepared_bad", "water_good"]
    assert review["comment"] == "Gravel"
    assert await reviewed_edges(app_conn, review["id"]) == {edges[1], edges[2]}


async def test_an_edge_run_twice_is_reviewed_once(
    client: httpx.AsyncClient, app_conn: Conn
) -> None:
    [edge] = await add_edges(app_conn, 1)
    route_id = await saved_route(client, [(edge, True), (edge, False)])

    response = await review_stretch(
        client, route_id, {"from_seq": 0, "to_seq": 1, "reasons": ["crowding_bad"]}
    )

    review = response.json()
    assert coords(review["geometry"]) == [(20.0, 63.8), (20.001, 63.8), (20.0, 63.8)]
    assert await reviewed_edges(app_conn, review["id"]) == {edge}


@pytest.mark.parametrize(
    "body",
    [
        {"from_seq": 0, "to_seq": 3, "reasons": ["green_bad"]},
        {"from_seq": 2, "to_seq": 1, "reasons": ["green_bad"]},
        {"from_seq": 0, "to_seq": 0, "reasons": []},
        {"from_seq": 0, "to_seq": 0, "reasons": ["lava_bad"]},
        {"from_seq": 0, "to_seq": 0, "reasons": ["green_bad", "green_good"]},
        {"from_seq": 0, "to_seq": 0, "reasons": ["green\x00bad"]},
        {"from_seq": 0, "to_seq": 0, "reasons": ["green_bad"], "comment": "Too\x00grey"},
    ],
    ids=[
        "past the end",
        "backwards",
        "no reason",
        "unknown reason",
        "both sides of a topic",
        "NUL in a reason",
        "NUL in the comment",
    ],
)
async def test_stretch_reviews_that_do_not_fit_are_refused(
    client: httpx.AsyncClient, app_conn: Conn, body: dict[str, Any]
) -> None:
    edges = await add_edges(app_conn, 3)
    route_id = await saved_route(client, [(edge, True) for edge in edges])

    response = await review_stretch(client, route_id, body)

    assert response.status_code == 422


async def test_reviews_are_listed_per_route_and_can_be_changed_and_deleted(
    client: httpx.AsyncClient, app_conn: Conn
) -> None:
    edges = await add_edges(app_conn, 3)
    route_id = await saved_route(client, [(edge, True) for edge in edges])
    later = await review_stretch(
        client, route_id, {"from_seq": 2, "to_seq": 2, "reasons": ["green_bad"]}
    )
    first = await review_stretch(
        client, route_id, {"from_seq": 0, "to_seq": 1, "reasons": ["safety_bad"]}
    )
    path = f"/logbook/routes/{route_id}/segment-reviews"

    listed = (await client.get(path)).json()
    assert [r["id"] for r in listed] == [first.json()["id"], later.json()["id"]]

    changed = await client.patch(
        f"/logbook/segment-reviews/{later.json()['id']}",
        json={"reasons": ["green_good", "lighting_good"], "comment": "Better in daylight"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["reasons"] == ["green_good", "lighting_good"]
    assert changed.json()["comment"] == "Better in daylight"
    assert changed.json()["updated_at"] > later.json()["updated_at"]

    assert (
        await client.delete(f"/logbook/segment-reviews/{first.json()['id']}")
    ).status_code == 204
    assert [r["id"] for r in (await client.get(path)).json()] == [later.json()["id"]]


async def test_other_users_routes_and_reviews_are_not_found(
    client: httpx.AsyncClient, app_conn: Conn
) -> None:
    [edge] = await add_edges(app_conn, 1)
    other = await add_user(app_conn, "other@example.com")
    cur = await app_conn.execute(
        """
        INSERT INTO app.routes
            (user_id, name, activity, shape, target_distance_m, geom, distance_m)
        VALUES (%s, 'Not yours', 'running', 'loop', 5000, %s, 50)
        RETURNING id
        """,
        (other, "SRID=4326;LINESTRING(20 63.8, 20.001 63.8)"),
    )
    row = await cur.fetchone()
    assert row is not None
    route_id = row[0]
    cur = await app_conn.execute(
        """
        INSERT INTO app.segment_reviews (user_id, route_id, activity, geom)
        SELECT user_id, id, activity, geom FROM app.routes WHERE id = %s
        RETURNING id
        """,
        (route_id,),
    )
    row = await cur.fetchone()
    assert row is not None
    review_path = f"/logbook/segment-reviews/{row[0]}"

    body = {"from_seq": 0, "to_seq": 0, "reasons": ["green_bad"]}
    assert (await review_stretch(client, route_id, body)).status_code == 404
    assert (await client.get(f"/logbook/routes/{route_id}/segment-reviews")).status_code == 404
    assert (await client.patch(review_path, json={"reasons": ["green_bad"]})).status_code == 404
    assert (await client.delete(review_path)).status_code == 404
