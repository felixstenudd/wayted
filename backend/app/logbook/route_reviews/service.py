from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection

from app.logbook.preferences.service import lock_weights
from app.routing.attributes import ROUTE_ATTRIBUTES

from . import queries
from .schemas import PreferenceChangeOut, RouteReviewIn, RouteReviewOut, SavedRouteReviewOut

STEP = Decimal("0.1")
# the planner slider's grid
GRID = Decimal("0.05")

_ORDER = {a.key: i for i, a in enumerate(ROUTE_ATTRIBUTES)}


class RouteNotFound(Exception):
    pass


class ReviewNotFound(Exception):
    pass


def nudge(weight: Decimal, steps: int) -> Decimal:
    """Move a weight one STEP per answer step, onto the slider grid, within -1..1."""
    moved = (weight + STEP * steps) / GRID
    return max(Decimal(-1), min(Decimal(1), moved.quantize(Decimal(1), ROUND_HALF_UP) * GRID))


async def save_review(
    user_id: UUID, route_id: int, review: RouteReviewIn, conn: AsyncConnection[Any]
) -> SavedRouteReviewOut:
    """
    Create or replace the user's review of their route, and nudge their weights by how the
    answers changed since the last save.
    """
    keys = {"user_id": user_id, "route_id": route_id}
    if await (await conn.execute(queries.OWNS_ROUTE, keys)).fetchone() is None:
        raise RouteNotFound("Route not found.")

    # Locks the review row, so a second save waits until this one has nudged.
    await conn.execute(queries.UPSERT_REVIEW, keys | {"comment": review.comment or None})
    cur = await conn.execute(queries.GET_ANSWERS, keys)
    before: dict[str, int] = dict(await cur.fetchall())
    await conn.execute(queries.DELETE_ANSWERS, keys)
    await conn.execute(
        queries.INSERT_ANSWERS,
        keys | {"attributes": list(review.answers), "answers": list(review.answers.values())},
    )

    steps = {
        key: review.answers.get(key, 0) - before.get(key, 0)
        for key in review.answers.keys() | before.keys()
    }
    changes = await _nudge_weights(
        user_id, {key: step for key, step in steps.items() if step != 0}, conn
    )
    return SavedRouteReviewOut(
        review=await get_review(user_id, route_id, conn), preference_changes=changes
    )


async def _nudge_weights(
    user_id: UUID, steps: dict[str, int], conn: AsyncConnection[Any]
) -> list[PreferenceChangeOut]:
    if not steps:
        return []
    await lock_weights(user_id, conn)
    cur = await conn.execute(queries.GET_WEIGHTS, {"user_id": user_id, "attributes": list(steps)})
    weights: dict[str, Decimal] = dict(await cur.fetchall())
    nudged = {key: nudge(weights.get(key, Decimal(0)), step) for key, step in steps.items()}

    kept = {key: weight for key, weight in nudged.items() if weight != 0}
    await conn.execute(
        queries.UPSERT_WEIGHTS,
        {"user_id": user_id, "attributes": list(kept), "weights": list(kept.values())},
    )
    await conn.execute(
        queries.DELETE_WEIGHTS,
        {"user_id": user_id, "attributes": [key for key in nudged if key not in kept]},
    )
    return [
        PreferenceChangeOut(
            attribute=key, before=float(weights.get(key, 0)), after=float(nudged[key])
        )
        for key in sorted(nudged, key=lambda key: _ORDER.get(key, len(_ORDER)))
    ]


async def get_review(user_id: UUID, route_id: int, conn: AsyncConnection[Any]) -> RouteReviewOut:
    cur = await conn.execute(queries.GET_REVIEW, {"user_id": user_id, "route_id": route_id})
    row = await cur.fetchone()
    if row is None or row[0] is None:
        raise ReviewNotFound("Review not found.")
    return RouteReviewOut.model_validate(row[0])


async def delete_review(user_id: UUID, route_id: int, conn: AsyncConnection[Any]) -> None:
    """Remove the review. The weights it nudged stay where they are."""
    cur = await conn.execute(queries.DELETE_REVIEW, {"user_id": user_id, "route_id": route_id})
    if await cur.fetchone() is None:
        raise ReviewNotFound("Review not found.")
