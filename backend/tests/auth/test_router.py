from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import service
from app.auth.router import router
from app.config import REFRESH_TOKEN_TTL_DAYS
from app.dependencies import api_conn


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[api_conn] = lambda: None
    with TestClient(app) as client:
        yield client


def _refresh_cookie(set_cookie: str) -> dict[str, str]:
    """Attributes of a Set-Cookie header, keyed by lowercase name."""
    attrs = {}
    for part in set_cookie.split(";"):
        key, _, value = part.strip().partition("=")
        attrs[key.lower()] = value
    return attrs


def test_login_sets_refresh_cookie_and_returns_only_access_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def login(email: str, password: str, db_conn: object) -> tuple[str, str]:
        return "access", "refresh"

    monkeypatch.setattr(service, "login", login)

    res = client.post("/auth/login", json={"email": "lina@example.se", "password": "secret123"})

    assert res.status_code == 200
    assert res.json() == {"access_token": "access", "token_type": "bearer"}
    cookie = _refresh_cookie(res.headers["set-cookie"])
    assert cookie["refresh_token"] == "refresh"
    assert cookie["path"] == "/"
    assert cookie["max-age"] == str(int(timedelta(days=REFRESH_TOKEN_TTL_DAYS).total_seconds()))
    assert cookie["samesite"] == "strict"
    assert "httponly" in cookie
    assert "secure" in cookie


def test_refresh_rotates_the_cookie(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seen = []

    async def refresh(refresh_token: str, db_conn: object) -> tuple[str, str]:
        seen.append(refresh_token)
        return "new-access", "new-refresh"

    monkeypatch.setattr(service, "refresh", refresh)

    res = client.post("/auth/refresh", headers={"Cookie": "refresh_token=old-refresh"})

    assert res.status_code == 200
    assert res.json()["access_token"] == "new-access"
    assert seen == ["old-refresh"]
    assert _refresh_cookie(res.headers["set-cookie"])["refresh_token"] == "new-refresh"


def test_refresh_without_cookie_is_unauthorized(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def refresh(refresh_token: str, db_conn: object) -> tuple[str, str]:
        raise AssertionError("service should not be called without a cookie")

    monkeypatch.setattr(service, "refresh", refresh)

    res = client.post("/auth/refresh")

    assert res.status_code == 401


def test_refresh_with_revoked_token_is_unauthorized(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def refresh(refresh_token: str, db_conn: object) -> tuple[str, str]:
        raise service.InvalidCredentials("Invalid refresh token")

    monkeypatch.setattr(service, "refresh", refresh)

    res = client.post("/auth/refresh", headers={"Cookie": "refresh_token=revoked"})

    assert res.status_code == 401


def test_logout_revokes_and_clears_the_cookie(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    revoked = []

    async def logout(refresh_token: str, db_conn: object) -> None:
        revoked.append(refresh_token)

    monkeypatch.setattr(service, "logout", logout)

    res = client.post("/auth/logout", headers={"Cookie": "refresh_token=current"})

    assert res.status_code == 204
    assert revoked == ["current"]
    cookie = _refresh_cookie(res.headers["set-cookie"])
    assert cookie["max-age"] == "0"
    assert cookie["path"] == "/"


def test_logout_without_cookie_still_clears_it(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def logout(refresh_token: str, db_conn: object) -> None:
        raise AssertionError("nothing to revoke without a cookie")

    monkeypatch.setattr(service, "logout", logout)

    res = client.post("/auth/logout")

    assert res.status_code == 204
    assert _refresh_cookie(res.headers["set-cookie"])["max-age"] == "0"
