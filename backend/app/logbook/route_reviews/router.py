"""
HTTP endpoints for the signed-in user's review of one of their routes
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.auth.dependencies import UserId
from app.dependencies import Conn

from . import service
from .schemas import RouteReviewIn, SavedRouteReviewOut

router = APIRouter(prefix="/routes/{route_id}/review")


@contextmanager
def _http_errors() -> Iterator[None]:
    """Translate service errors into HTTP responses."""
    try:
        yield
    except (service.RouteNotFound, service.ReviewNotFound) as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from None


@router.put(
    "",
    responses={status.HTTP_404_NOT_FOUND: {"description": "No such route among the user's"}},
)
async def save_review(
    user_id: UserId, route_id: int, body: RouteReviewIn, db_conn: Conn
) -> SavedRouteReviewOut:
    """
    Create or replace the review. Each answer that changed moves the user's weight for that
    attribute by 0.1 per step; the response lists those changes.
    """
    with _http_errors():
        return await service.save_review(user_id, route_id, body, db_conn)


_NO_REVIEW: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"description": "The route has no review by the user"}
}


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, responses=_NO_REVIEW)
async def delete_review(user_id: UserId, route_id: int, db_conn: Conn) -> None:
    """Delete the review. The weights it moved are kept."""
    with _http_errors():
        await service.delete_review(user_id, route_id, db_conn)
