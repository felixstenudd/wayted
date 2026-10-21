from typing import Any
from uuid import UUID

from psycopg import AsyncConnection

from . import queries
from .schemas import PreferencesOut


async def get_preferences(user_id: UUID, conn: AsyncConnection[Any]) -> PreferencesOut:
    cur = await conn.execute(queries.GET_WEIGHTS, {"user_id": user_id})
    return PreferencesOut(weights={key: float(weight) for key, weight in await cur.fetchall()})


async def lock_weights(user_id: UUID, conn: AsyncConnection[Any]) -> None:
    """Wait until no other transaction is writing the user's weights; hold that until commit."""
    await conn.execute(queries.LOCK_WEIGHTS, {"user_id": user_id})


async def save_preferences(
    user_id: UUID, weights: dict[str, float], conn: AsyncConnection[Any]
) -> PreferencesOut:
    """Replace the user's default weights."""
    await lock_weights(user_id, conn)
    await conn.execute(queries.DELETE_WEIGHTS, {"user_id": user_id})
    await conn.execute(
        queries.INSERT_WEIGHTS,
        {"user_id": user_id, "attributes": list(weights), "weights": list(weights.values())},
    )
    return await get_preferences(user_id, conn)
