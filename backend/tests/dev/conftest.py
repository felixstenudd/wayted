import os
from collections.abc import AsyncIterator

import httpx
import pytest
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

# app.config reads these at import. The tests never use them: connections come from api_pool.
for name in (
    "JWT_SECRET",
    "WAYTED_API_PASSWORD",
    "WAYTED_DOWNLOADER_PASSWORD",
    "WAYTED_MAPPER_PASSWORD",
    "WAYTED_ENRICHER_PASSWORD",
):
    os.environ.setdefault(name, "unused")

from app.dependencies import api_conn  # noqa: E402
from app.dev.main import app  # noqa: E402


@pytest.fixture
async def client(
    api_pool: AsyncConnectionPool[AsyncConnection[TupleRow]],
) -> AsyncIterator[httpx.AsyncClient]:
    """Calls the dev app in-process, with its connections taken from the wayted_api test pool."""

    async def test_conn() -> AsyncIterator[AsyncConnection[TupleRow]]:
        async with api_pool.connection() as conn:
            yield conn

    app.dependency_overrides[api_conn] = test_conn
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://dev") as http:
        yield http
    app.dependency_overrides.clear()
