"""FastAPI dependencies shared by the API modules."""

from collections.abc import AsyncIterator
from typing import Annotated, TypeAlias

from fastapi import Depends
from psycopg import AsyncConnection
from psycopg.rows import TupleRow

from app import db
from app.config import API_ROLE


async def api_conn() -> AsyncIterator[AsyncConnection[TupleRow]]:
    async with db.connection(API_ROLE) as conn:
        yield conn


# The connection commits when it goes back to the pool. scope="function" hands it back as the
# endpoint returns, so a client never gets an answer for a write that is not stored yet.
Conn: TypeAlias = Annotated[  # noqa: UP040
    AsyncConnection[TupleRow], Depends(api_conn, scope="function")
]
