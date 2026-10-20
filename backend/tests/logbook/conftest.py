import os
from collections.abc import AsyncIterator

import pytest
from psycopg import AsyncConnection
from psycopg.rows import TupleRow

# app.config reads these at import time.
for name in (
    "JWT_SECRET",
    "WAYTED_API_PASSWORD",
    "WAYTED_DOWNLOADER_PASSWORD",
    "WAYTED_MAPPER_PASSWORD",
    "WAYTED_ENRICHER_PASSWORD",
):
    os.environ.setdefault(name, "test")

type Conn = AsyncConnection[TupleRow]


@pytest.fixture
async def app_conn(admin_conn: Conn) -> AsyncIterator[Conn]:
    """admin_conn with the app schema emptied too."""
    await admin_conn.execute("TRUNCATE app.users RESTART IDENTITY CASCADE")
    yield admin_conn
