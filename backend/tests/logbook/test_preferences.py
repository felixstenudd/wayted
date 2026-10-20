import httpx
import pytest
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from starlette.types import Message, Receive, Scope, Send

from app.main import app

pytestmark = pytest.mark.db

type Conn = AsyncConnection[TupleRow]


async def weights(client: httpx.AsyncClient) -> dict[str, float]:
    response = await client.get("/logbook/preferences")
    assert response.status_code == 200
    body: dict[str, float] = response.json()["weights"]
    return body


async def test_a_new_user_has_no_preferences(client: httpx.AsyncClient) -> None:
    assert await weights(client) == {}


async def test_saving_replaces_all_weights_and_drops_zeros(client: httpx.AsyncClient) -> None:
    await client.put("/logbook/preferences", json={"weights": {"green": 0.5, "water": -0.25}})

    response = await client.put("/logbook/preferences", json={"weights": {"water": 1, "nature": 0}})

    assert response.status_code == 200
    assert response.json() == {"weights": {"water": 1.0}}
    assert await weights(client) == {"water": 1.0}


@pytest.mark.parametrize("weights_in", [{"lava": 0.5}, {"green": 1.5}])
async def test_unknown_attributes_and_weights_out_of_range_are_refused(
    client: httpx.AsyncClient, weights_in: dict[str, float]
) -> None:
    response = await client.put("/logbook/preferences", json={"weights": weights_in})

    assert response.status_code == 422


async def test_saving_is_committed_before_the_answer_is_sent(
    client: httpx.AsyncClient, app_conn: Conn
) -> None:
    visible: list[int] = []

    async def counting(scope: Scope, receive: Receive, send: Send) -> None:
        async def send_counted(message: Message) -> None:
            if message["type"] == "http.response.start":
                cur = await app_conn.execute("SELECT count(*) FROM app.user_preferences")
                row = await cur.fetchone()
                assert row is not None
                visible.append(row[0])
            await send(message)

        await app(scope, receive, send_counted)

    transport = httpx.ASGITransport(app=counting)
    async with httpx.AsyncClient(transport=transport, base_url="http://api") as http:
        response = await http.put("/logbook/preferences", json={"weights": {"green": 0.5}})

    assert response.status_code == 200
    assert visible == [1]
