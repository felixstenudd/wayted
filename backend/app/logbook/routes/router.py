"""
HTTP endpoints for the signed-in user's saved routes
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.auth.dependencies import UserId
from app.dependencies import Conn

from . import service
from .schemas import RenameIn, RouteIn, RouteOut, RouteSummaryOut

router = APIRouter(prefix="/routes")

_STATUS_CODES: dict[type[service.RouteError], int] = {
    service.InvalidRoute: status.HTTP_422_UNPROCESSABLE_CONTENT,
    service.RouteNotFound: status.HTTP_404_NOT_FOUND,
}

_NOT_FOUND: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"description": "No such route among the user's"}
}


@contextmanager
def _http_errors() -> Iterator[None]:
    """Translate service errors into HTTP responses."""
    try:
        yield
    except service.RouteError as e:
        raise HTTPException(_STATUS_CODES[type(e)], str(e)) from None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_route(user_id: UserId, body: RouteIn, db_conn: Conn) -> RouteOut:
    """Save a route given as edges in order. The edges must connect and allow the activity."""
    with _http_errors():
        return await service.create_route(user_id, body, db_conn)


@router.get("")
async def list_routes(user_id: UserId, db_conn: Conn) -> list[RouteSummaryOut]:
    """The user's routes, newest first."""
    return await service.list_routes(user_id, db_conn)


@router.get("/{route_id}", responses=_NOT_FOUND)
async def get_route(user_id: UserId, route_id: int, db_conn: Conn) -> RouteOut:
    with _http_errors():
        return await service.get_route(user_id, route_id, db_conn)


@router.patch("/{route_id}", responses=_NOT_FOUND)
async def rename_route(
    user_id: UserId, route_id: int, body: RenameIn, db_conn: Conn
) -> RouteSummaryOut:
    with _http_errors():
        return await service.rename_route(user_id, route_id, body.name, db_conn)


@router.delete("/{route_id}", status_code=status.HTTP_204_NO_CONTENT, responses=_NOT_FOUND)
async def delete_route(user_id: UserId, route_id: int, db_conn: Conn) -> None:
    with _http_errors():
        await service.delete_route(user_id, route_id, db_conn)
