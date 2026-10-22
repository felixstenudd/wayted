from collections.abc import AsyncIterator, Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import current_user
from app.dependencies import api_conn
from app.enrichment.definitions import ATTRIBUTES
from app.routing.router import router

LOOP: dict[str, Any] = {
    "activity": "running",
    "shape": "loop",
    "start": {"lon": 20.26, "lat": 63.82},
    "target_distance_m": 10_000,
    "preferences": {"nature": 0.5, "green": -0.37},
}


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


async def no_database() -> AsyncIterator[None]:
    """FastAPI opens dependencies before it rejects the body; a rejected request runs no query."""
    yield None


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    app.dependency_overrides[current_user] = uuid4
    app.dependency_overrides[api_conn] = no_database
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(
    ("method", "path"), [("GET", "/routing/attributes"), ("POST", "/routing/routes")]
)
def test_needs_a_signed_in_user(app: FastAPI, method: str, path: str) -> None:
    with TestClient(app) as client:
        res = client.request(method, path, json=LOOP)

    assert res.status_code == 401


def test_attributes_are_listed_in_display_order_with_groups(client: TestClient) -> None:
    res = client.get("/routing/attributes")

    assert res.status_code == 200
    assert [(a["key"], a["group"]) for a in res.json()] == [
        ("green", "surroundings"),
        ("nature", "surroundings"),
        ("water", "surroundings"),
        ("quiet_streets", "streets"),
        ("sights", "sights"),
        ("bridges", "sights"),
        ("prepared", "surface"),
        ("hills", "terrain"),
    ]


def test_attributes_are_scored_when_the_enricher_scores_them(client: TestClient) -> None:
    res = client.get("/routing/attributes")

    scored = {a["key"] for a in res.json() if a["scored"]}
    assert scored == {a.key for a in ATTRIBUTES}


@pytest.mark.parametrize(
    "change",
    [
        {"finish": {"lon": 20.3, "lat": 63.83}},
        {"shape": "point_to_point"},
        {"activity": "walking"},
        {"start": {"lon": 181, "lat": 63.82}},
        {"start": {"lon": 20.26, "lat": -91}},
        {"target_distance_m": None},
        {"target_distance_m": 999},
        {"target_distance_m": 200_001},
        {"preferences": {"nature": 1.01}},
        {"preferences": {"nature": -1.01}},
        {"preferences": {"unknown": 0.5}},
    ],
    ids=[
        "finish on a loop",
        "no finish on point to point",
        "unknown activity",
        "longitude out of range",
        "latitude out of range",
        "no distance on a loop",
        "distance too short",
        "distance too long",
        "weight above 1",
        "weight below -1",
        "unknown attribute",
    ],
)
def test_an_invalid_request_is_rejected(client: TestClient, change: dict[str, Any]) -> None:
    res = client.post("/routing/routes", json={**LOOP, **change})

    assert res.status_code == 422
