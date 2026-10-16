from uuid import UUID

from psycopg import AsyncConnection

from app.logbook.reviews.queries import (
    CREATE_ROUTE_REVIEW,
    GET_ROUTE_REVIEW,
    LIST_ROUTE_REVIEWS,
    UPDATE_ROUTE_REVIEW,
    DELETE_ROUTE_REVIEW,
    GET_ROUTE_REVIEW_SUMMARY,
    CREATE_SEGMENT_RATING,
    GET_SEGMENT_RATING,
    DELETE_SEGMENT_RATING,
    GET_SEGMENT_RATING_SUMMARY,
)
from app.logbook.routes.services import get_route, RouteNotFound


class ReviewError(Exception):
    """Base exception for review services."""


class ReviewInvalidInput(ReviewError):
    pass


class ReviewNotFound(ReviewError):
    pass


def _validate_rating(rating: int) -> None:
    if not 1 <= rating <= 5:
        raise ReviewInvalidInput("Rating must be between 1 and 5.")


async def create_route_review(
    user_id: UUID,
    route_id: int,
    rating: int,
    comment: str | None,
    db_conn: AsyncConnection,
):
    _validate_rating(rating)

    await get_route(route_id, user_id, db_conn)

    cur = await db_conn.execute(
        CREATE_ROUTE_REVIEW,
        (user_id, route_id, rating, comment),
    )
    return await cur.fetchone()


async def get_route_review(
    user_id: UUID,
    route_id: int,
    db_conn: AsyncConnection,
):
    cur = await db_conn.execute(
        GET_ROUTE_REVIEW,
        (user_id, route_id),
    )
    row = await cur.fetchone()

    if row is None:
        raise ReviewNotFound("Review not found.")

    return row


async def list_route_reviews(
    route_id: int,
    limit: int,
    offset: int,
    db_conn: AsyncConnection,
):
    _validate_pagination(limit, offset)

    cur = await db_conn.execute(
        LIST_ROUTE_REVIEWS,
        (route_id, limit, offset),
    )
    return await cur.fetchall()


async def update_route_review(
    user_id: UUID,
    route_id: int,
    rating: int,
    comment: str | None,
    db_conn: AsyncConnection,
):
    _validate_rating(rating)

    cur = await db_conn.execute(
        UPDATE_ROUTE_REVIEW,
        (rating, comment, user_id, route_id),
    )
    row = await cur.fetchone()

    if row is None:
        raise ReviewNotFound("Review not found.")

    return row


async def delete_route_review(
    user_id: UUID,
    route_id: int,
    db_conn: AsyncConnection,
):
    cur = await db_conn.execute(
        DELETE_ROUTE_REVIEW,
        (user_id, route_id),
    )
    row = await cur.fetchone()

    if row is None:
        raise ReviewNotFound("Review not found.")

    return row


async def get_route_review_summary(
    route_id: int,
    db_conn: AsyncConnection,
):
    cur = await db_conn.execute(
        GET_ROUTE_REVIEW_SUMMARY,
        (route_id,),
    )
    return await cur.fetchone()


async def create_segment_rating(
    user_id: UUID,
    segment_id: int,
    rating: int,
    db_conn: AsyncConnection,
):
    _validate_rating(rating)

    cur = await db_conn.execute(
        CREATE_SEGMENT_RATING,
        (user_id, segment_id, rating),
    )
    row = await cur.fetchone()

    if row is None:
        raise ReviewNotFound("Segment not found.")

    return row


async def get_segment_rating(
    user_id: UUID,
    segment_id: int,
    db_conn: AsyncConnection,
):
    cur = await db_conn.execute(
        GET_SEGMENT_RATING,
        (user_id, segment_id),
    )
    row = await cur.fetchone()

    if row is None:
        raise ReviewNotFound("Segment rating not found.")

    return row


async def delete_segment_rating(
    user_id: UUID,
    segment_id: int,
    db_conn: AsyncConnection,
):
    cur = await db_conn.execute(
        DELETE_SEGMENT_RATING,
        (user_id, segment_id),
    )
    row = await cur.fetchone()

    if row is None:
        raise ReviewNotFound("Segment rating not found.")

    return row


async def get_segment_rating_summary(
    segment_id: int,
    db_conn: AsyncConnection,
):
    cur = await db_conn.execute(
        GET_SEGMENT_RATING_SUMMARY,
        (segment_id,),
    )
    return await cur.fetchone()


def _validate_pagination(limit: int, offset: int) -> None:
    if not 1 <= limit <= 100:
        raise ReviewInvalidInput("Limit must be between 1 and 100.")

    if offset < 0:
        raise ReviewInvalidInput("Offset cannot be negative.")
