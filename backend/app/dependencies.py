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


Conn: TypeAlias = Annotated[AsyncConnection[TupleRow], Depends(api_conn)]  # noqa: UP040
