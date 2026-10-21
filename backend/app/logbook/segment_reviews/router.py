"""
HTTP endpoints for the signed-in user's reviews of stretches of their routes
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.auth.dependencies import UserId
from app.dependencies import Conn

from . import service
from .schemas import ReasonOut, SegmentReviewChangeIn, SegmentReviewIn, SegmentReviewOut

router = APIRouter()

_STATUS_CODES: dict[type[service.SegmentReviewError], int] = {
    service.InvalidReview: status.HTTP_422_UNPROCESSABLE_CONTENT,
    service.NotFound: status.HTTP_404_NOT_FOUND,
}

_NO_ROUTE: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"description": "No such route among the user's"}
}
_NO_REVIEW: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"description": "No such review among the user's"}
}


@contextmanager
def _http_errors() -> Iterator[None]:
    """Translate service errors into HTTP responses."""
    try:
        yield
    except service.SegmentReviewError as e:
        raise HTTPException(_STATUS_CODES[type(e)], str(e)) from None


@router.get("/review-reasons")
async def list_reasons(_: UserId, db_conn: Conn) -> list[ReasonOut]:
    """What a stretch review can say."""
    return await service.list_reasons(db_conn)


@router.get("/routes/{route_id}/segment-reviews", responses=_NO_ROUTE)
async def list_reviews(user_id: UserId, route_id: int, db_conn: Conn) -> list[SegmentReviewOut]:
    """The user's stretch reviews on this route, in route order."""
    with _http_errors():
        return await service.list_reviews(user_id, route_id, db_conn)


@router.post(
    "/routes/{route_id}/segment-reviews", status_code=status.HTTP_201_CREATED, responses=_NO_ROUTE
)
async def create_review(
    user_id: UserId, route_id: int, body: SegmentReviewIn, db_conn: Conn
) -> SegmentReviewOut:
    """Review the stretch from edge from_seq to edge to_seq of the route."""
    with _http_errors():
        return await service.create_review(user_id, route_id, body, db_conn)


@router.patch("/segment-reviews/{review_id}", responses=_NO_REVIEW)
async def change_review(
    user_id: UserId, review_id: int, body: SegmentReviewChangeIn, db_conn: Conn
) -> SegmentReviewOut:
    """Replace the reasons and the comment. The stretch cannot change."""
    with _http_errors():
        return await service.change_review(user_id, review_id, body, db_conn)


@router.delete(
    "/segment-reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT, responses=_NO_REVIEW
)
async def delete_review(user_id: UserId, review_id: int, db_conn: Conn) -> None:
    with _http_errors():
        await service.delete_review(user_id, review_id, db_conn)
