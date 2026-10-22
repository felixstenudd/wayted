import os
from collections.abc import AsyncIterator
from uuid import UUID

import httpx
import pytest
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

# app.config reads these at import time.
for name in (
    "JWT_SECRET",
    "WAYTED_API_PASSWORD",
    "WAYTED_DOWNLOADER_PASSWORD",
    "WAYTED_MAPPER_PASSWORD",
    "WAYTED_ENRICHER_PASSWORD",
):
    os.environ.setdefault(name, "test")

from app.auth.dependencies import current_user  # noqa: E402
from app.dependencies import api_conn  # noqa: E402
from app.main import app  # noqa: E402

from .app_data import add_user  # noqa: E402

type Conn = AsyncConnection[TupleRow]
type Pool = AsyncConnectionPool[Conn]


@pytest.fixture
async def app_conn(admin_conn: Conn) -> AsyncIterator[Conn]:
    """admin_conn with the app schema emptied too."""
    await admin_conn.execute("TRUNCATE app.users RESTART IDENTITY CASCADE")
    yield admin_conn


@pytest.fixture
async def user_id(app_conn: Conn) -> UUID:
    return await add_user(app_conn)


@pytest.fixture
async def client(api_pool: Pool, user_id: UUID) -> AsyncIterator[httpx.AsyncClient]:
    """Calls the API in-process as `user_id`, with connections from the wayted_api test pool."""

    async def test_conn() -> AsyncIterator[Conn]:
        async with api_pool.connection() as conn:
            yield conn

    app.dependency_overrides[api_conn] = test_conn
    app.dependency_overrides[current_user] = lambda: user_id
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://api") as http:
        yield http
    app.dependency_overrides.clear()
