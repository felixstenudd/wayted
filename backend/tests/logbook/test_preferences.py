import httpx
import pytest

pytestmark = pytest.mark.db


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
