from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import current_user
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


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    app.dependency_overrides[current_user] = uuid4
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
    ]


def test_attributes_are_scored_when_the_enricher_scores_them(client: TestClient) -> None:
    res = client.get("/routing/attributes")

    scored = {a["key"] for a in res.json() if a["scored"]}
    assert scored == {a.key for a in ATTRIBUTES}


def test_a_valid_request_is_not_implemented_yet(client: TestClient) -> None:
    res = client.post("/routing/routes", json=LOOP)

    assert res.status_code == 501
    assert res.json() == {"detail": "Route generation is not available yet."}


def test_point_to_point_with_a_finish_is_valid(client: TestClient) -> None:
    body = {**LOOP, "shape": "point_to_point", "finish": {"lon": 20.3, "lat": 63.83}}

    assert client.post("/routing/routes", json=body).status_code == 501


@pytest.mark.parametrize(
    "change",
    [
        {"finish": {"lon": 20.3, "lat": 63.83}},
        {"shape": "point_to_point"},
        {"activity": "walking"},
        {"start": {"lon": 181, "lat": 63.82}},
        {"start": {"lon": 20.26, "lat": -91}},
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
