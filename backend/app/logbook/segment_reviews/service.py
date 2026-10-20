from collections import Counter
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import dict_row

from . import queries
from .schemas import ReasonOut, SegmentReviewChangeIn, SegmentReviewIn, SegmentReviewOut


class SegmentReviewError(Exception):
    """Base for errors the router turns into HTTP responses."""


class InvalidReview(SegmentReviewError):
    pass


class NotFound(SegmentReviewError):
    pass


async def list_reasons(conn: AsyncConnection[Any]) -> list[ReasonOut]:
    cur = conn.cursor(row_factory=dict_row)
    await cur.execute(queries.LIST_REASONS)
    return [ReasonOut.model_validate(row) for row in await cur.fetchall()]


async def create_review(
    user_id: UUID, route_id: int, review: SegmentReviewIn, conn: AsyncConnection[Any]
) -> SegmentReviewOut:
    """Review a stretch of the user's route; the activity is the route's."""
    keys = {"user_id": user_id, "route_id": route_id}
    row = await (await conn.execute(queries.LOCK_ROUTE_EDGE_COUNT, keys)).fetchone()
    if row is None:
        raise NotFound("Route not found.")
    if review.to_seq >= row[0]:
        raise InvalidReview(f"The route has {row[0]} edges; the stretch ends after them.")
    reasons = await _checked_reasons(review.reasons, conn)

    stretch = keys | {"from_seq": review.from_seq, "to_seq": review.to_seq}
    cur = await conn.execute(queries.CREATE_REVIEW, stretch | {"comment": review.comment or None})
    created = await cur.fetchone()
    assert created is not None
    review_id: int = created[0]
    await conn.execute(queries.ADD_EDGES, stretch | {"review_id": review_id})
    await conn.execute(queries.ADD_REASONS, {"review_id": review_id, "reasons": reasons})
    return await get_review(user_id, review_id, conn)


async def change_review(
    user_id: UUID, review_id: int, change: SegmentReviewChangeIn, conn: AsyncConnection[Any]
) -> SegmentReviewOut:
    """Replace the reasons and the comment. The changed review becomes the user's latest."""
    reasons = await _checked_reasons(change.reasons, conn)
    keys = {"user_id": user_id, "review_id": review_id}
    cur = await conn.execute(queries.CHANGE_REVIEW, keys | {"comment": change.comment or None})
    if await cur.fetchone() is None:
        raise NotFound("Review not found.")
    await conn.execute(queries.DELETE_REASONS, keys)
    await conn.execute(queries.ADD_REASONS, keys | {"reasons": reasons})
    return await get_review(user_id, review_id, conn)


async def _checked_reasons(reasons: list[str], conn: AsyncConnection[Any]) -> list[str]:
    """The reasons without repeats, if all are known and no two share a topic."""
    unique = sorted(set(reasons))
    cur = await conn.execute(queries.REASON_TOPICS, {"reasons": unique})
    topics: dict[str, str] = dict(await cur.fetchall())
    unknown = set(unique) - topics.keys()
    if unknown:
        raise InvalidReview(f"Unknown reasons: {', '.join(sorted(unknown))}.")
    shared = sorted(topic for topic, n in Counter(topics.values()).items() if n > 1)
    if shared:
        raise InvalidReview(f"Choose one reason per topic: {', '.join(shared)}.")
    return unique


async def get_review(user_id: UUID, review_id: int, conn: AsyncConnection[Any]) -> SegmentReviewOut:
    cur = conn.cursor(row_factory=dict_row)
    await cur.execute(queries.GET_REVIEW, {"user_id": user_id, "review_id": review_id})
    row = await cur.fetchone()
    if row is None:
        raise NotFound("Review not found.")
    return SegmentReviewOut.model_validate(row)


async def list_reviews(
    user_id: UUID, route_id: int, conn: AsyncConnection[Any]
) -> list[SegmentReviewOut]:
    """The user's reviews of stretches of their route, in route order."""
    keys = {"user_id": user_id, "route_id": route_id}
    if await (await conn.execute(queries.ROUTE_EDGE_COUNT, keys)).fetchone() is None:
        raise NotFound("Route not found.")
    cur = conn.cursor(row_factory=dict_row)
    await cur.execute(queries.LIST_REVIEWS, keys)
    return [SegmentReviewOut.model_validate(row) for row in await cur.fetchall()]


async def delete_review(user_id: UUID, review_id: int, conn: AsyncConnection[Any]) -> None:
    keys = {"user_id": user_id, "review_id": review_id}
    if await (await conn.execute(queries.DELETE_REVIEW, keys)).fetchone() is None:
        raise NotFound("Review not found.")
