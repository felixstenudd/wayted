"""FastAPI dependencies shared by the API modules."""

from typing import Annotated, TypeAlias

from fastapi import Depends
from psycopg import AsyncConnection

from app import db
from app.config import API_ROLE


async def api_conn():
    async with db.connection(API_ROLE) as conn:
        yield conn


Conn: TypeAlias = Annotated[AsyncConnection, Depends(api_conn)]  # noqa: UP040
