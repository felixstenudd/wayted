from decimal import Decimal
from typing import Any

import httpx
import pytest
from psycopg import AsyncConnection
from psycopg.rows import TupleRow

from app.logbook.route_reviews.service import nudge

from .app_data import add_edges

type Conn = AsyncConnection[TupleRow]


@pytest.mark.parametrize(
    ("weight", "steps", "nudged"),
    [
        ("0", 1, "0.1"),
        ("0.37", 1, "0.45"),
        ("0.1", -2, "-0.1"),
        ("0.95", 1, "1"),
        ("1", 1, "1"),
        ("-0.95", -2, "-1"),
    ],
)
def test_a_nudge_moves_a_tenth_per_step_on_the_slider_grid(
    weight: str, steps: int, nudged: str
) -> None:
    assert nudge(Decimal(weight), steps) == Decimal(nudged)


async def saved_route(client: httpx.AsyncClient, app_conn: Conn) -> str:
    [edge] = await add_edges(app_conn, 1)
    response = await client.post(
        "/logbook/routes",
        json={
            "name": "Morning loop",
            "activity": "running",
            "shape": "loop",
            "target_distance_m": 5000,
            "edges": [{"edge_id": edge, "forward": True}],
        },
    )
    assert response.status_code == 201
    return f"/logbook/routes/{response.json()['id']}"


async def review(client: httpx.AsyncClient, path: str, body: dict[str, Any]) -> dict[str, Any]:
    response = await client.put(f"{path}/review", json=body)
    assert response.status_code == 200, response.text
    saved: dict[str, Any] = response.json()
    return saved


async def weights(client: httpx.AsyncClient) -> dict[str, float]:
    body: dict[str, float] = (await client.get("/logbook/preferences")).json()["weights"]
    return body


@pytest.mark.db
async def test_a_review_nudges_the_weights_it_asks_to_change(
    client: httpx.AsyncClient, app_conn: Conn
) -> None:
    path = await saved_route(client, app_conn)

    saved = await review(client, path, {"answers": {"green": 1, "water": 0}, "comment": " Nice "})

    assert saved["preference_changes"] == [{"attribute": "green", "before": 0.0, "after": 0.1}]
    assert saved["review"]["answers"] == {"green": 1, "water": 0}
    assert saved["review"]["comment"] == "Nice"
    assert await weights(client) == {"green": 0.1}
    assert (await client.get(path)).json()["review"] == saved["review"]


@pytest.mark.db
async def test_editing_a_review_applies_only_the_difference(
    client: httpx.AsyncClient, app_conn: Conn
) -> None:
    path = await saved_route(client, app_conn)
    await review(client, path, {"answers": {"green": 1, "water": -1}})

    saved = await review(client, path, {"answers": {"green": -1, "water": -1}})

    assert saved["preference_changes"] == [{"attribute": "green", "before": 0.1, "after": -0.1}]
    assert saved["review"]["answers"] == {"green": -1, "water": -1}
    assert saved["review"]["comment"] is None
    assert await weights(client) == {"green": -0.1, "water": -0.1}


@pytest.mark.db
async def test_a_weight_at_the_end_of_the_scale_stays_there(
    client: httpx.AsyncClient, app_conn: Conn
) -> None:
    path = await saved_route(client, app_conn)
    await client.put("/logbook/preferences", json={"weights": {"green": 1}})

    saved = await review(client, path, {"answers": {"green": 1}})

    assert saved["preference_changes"] == [{"attribute": "green", "before": 1.0, "after": 1.0}]


@pytest.mark.db
async def test_deleting_a_review_keeps_the_weights(
    client: httpx.AsyncClient, app_conn: Conn
) -> None:
    path = await saved_route(client, app_conn)
    await review(client, path, {"answers": {"water": 1}})

    assert (await client.delete(f"{path}/review")).status_code == 204

    assert await weights(client) == {"water": 0.1}
    assert (await client.get(path)).json()["review"] is None
    assert (await client.delete(f"{path}/review")).status_code == 404


@pytest.mark.db
@pytest.mark.parametrize(
    "answers",
    [{}, {"bridges": 1}, {"lava": 1}, {"green": 2}],
    ids=["none", "unscored", "unknown", "two"],
)
async def test_reviews_answer_scored_attributes_only(
    client: httpx.AsyncClient, app_conn: Conn, answers: dict[str, int]
) -> None:
    path = await saved_route(client, app_conn)

    response = await client.put(f"{path}/review", json={"answers": answers})

    assert response.status_code == 422


@pytest.mark.db
async def test_routes_you_do_not_have_cannot_be_reviewed(client: httpx.AsyncClient) -> None:
    response = await client.put("/logbook/routes/999/review", json={"answers": {"green": 1}})

    assert response.status_code == 404
