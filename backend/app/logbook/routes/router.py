"""
HTTP endpoints for the signed-in user's saved routes
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi import APIRouter, HTTPException, Response, status

from app.auth.dependencies import UserId
from app.dependencies import Conn

from . import service
from .export import FIT_MEDIA_TYPE, GPX_MEDIA_TYPE, ExportFile
from .schemas import RenameIn, RouteIn, RouteOut, RouteSummaryOut

router = APIRouter(prefix="/routes")

_STATUS_CODES: dict[type[service.RouteError], int] = {
    service.InvalidRoute: status.HTTP_422_UNPROCESSABLE_CONTENT,
    service.RouteNotFound: status.HTTP_404_NOT_FOUND,
}

_NOT_FOUND: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"description": "No such route among the user's"}
}


# A file to save rather than JSON; the response_class keeps FastAPI from also listing JSON.
_GPX_FILE: dict[int | str, dict[str, Any]] = {
    status.HTTP_200_OK: {
        "description": "The route as a GPX 1.1 track",
        "content": {GPX_MEDIA_TYPE: {"schema": {"type": "string"}}},
    }
}

_FIT_FILE: dict[int | str, dict[str, Any]] = {
    status.HTTP_200_OK: {
        "description": "The route as a FIT course",
        "content": {FIT_MEDIA_TYPE: {"schema": {"type": "string", "format": "binary"}}},
    }
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


@router.get("/{route_id}/gpx", response_class=Response, responses=_GPX_FILE | _NOT_FOUND)
async def export_gpx(user_id: UserId, route_id: int, db_conn: Conn) -> Response:
    """The route as a GPX file to download, for apps and watches that follow a track."""
    with _http_errors():
        return _attachment(await service.export_gpx(user_id, route_id, db_conn))


@router.get("/{route_id}/fit", response_class=Response, responses=_FIT_FILE | _NOT_FOUND)
async def export_fit(user_id: UserId, route_id: int, db_conn: Conn) -> Response:
    """The route as a FIT course to download, for Garmin watches and bike computers to follow
    with turn prompts."""
    with _http_errors():
        return _attachment(await service.export_fit(user_id, route_id, db_conn))


def _attachment(file: ExportFile) -> Response:
    # The file name is a slug, so it needs no quoting beyond the quotes.
    return Response(
        file.content,
        media_type=file.media_type,
        headers={"Content-Disposition": f'attachment; filename="{file.filename}"'},
    )
