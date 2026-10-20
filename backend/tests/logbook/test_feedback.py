from datetime import UTC, datetime
from typing import Any

import pytest
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from app.enrichment import enrich_pending

from .app_data import add_edges, add_segment_review, add_user

pytestmark = pytest.mark.db

type Conn = AsyncConnection[TupleRow]
type Pool = AsyncConnectionPool[Conn]

EARLIER = datetime(2026, 10, 1, tzinfo=UTC)
LATER = datetime(2026, 10, 2, tzinfo=UTC)


async def feedback(conn: Conn, pool: Pool) -> dict[int, Any]:
    await enrich_pending(pool.connection)
    cur = await conn.execute("SELECT id, feedback FROM graph.edges")
    return dict(await cur.fetchall())


def votes(up: int, down: int) -> dict[str, int]:
    return {"up": up, "down": down}


async def test_votes_are_counted_per_edge_activity_and_topic(
    app_conn: Conn, enricher_pool: Pool
) -> None:
    a, b, c = await add_edges(app_conn, 3)
    runner = await add_user(app_conn, "runner@example.com")
    cyclist = await add_user(app_conn, "cyclist@example.com")
    await add_segment_review(app_conn, runner, None, [a, b], ["green_bad", "access_bad"])
    await add_segment_review(app_conn, cyclist, None, [b], ["green_good"])
    await add_segment_review(app_conn, cyclist, None, [b], ["green_bad"], activity="cycling")

    assert await feedback(app_conn, enricher_pool) == {
        a: {"running": {"green": votes(0, 1), "access": votes(0, 1)}},
        b: {
            "running": {"green": votes(1, 1), "access": votes(0, 1)},
            "cycling": {"green": votes(0, 1)},
        },
        c: {},
    }


async def test_a_user_counts_once_per_topic_with_their_latest_review(
    app_conn: Conn, enricher_pool: Pool
) -> None:
    [edge] = await add_edges(app_conn, 1)
    runner = await add_user(app_conn)
    await add_segment_review(
        app_conn, runner, None, [edge], ["green_bad", "lighting_bad"], updated_at=EARLIER
    )
    await add_segment_review(app_conn, runner, None, [edge], ["green_good"], updated_at=LATER)
    await add_segment_review(app_conn, runner, None, [edge], ["green_good"], updated_at=LATER)

    assert (await feedback(app_conn, enricher_pool))[edge] == {
        "running": {"green": votes(1, 0), "lighting": votes(0, 1)}
    }


async def test_a_deleted_review_stops_counting(app_conn: Conn, enricher_pool: Pool) -> None:
    [edge] = await add_edges(app_conn, 1)
    runner = await add_user(app_conn)
    review_id = await add_segment_review(app_conn, runner, None, [edge], ["safety_bad"])
    await feedback(app_conn, enricher_pool)

    await app_conn.execute("DELETE FROM app.segment_reviews WHERE id = %s", (review_id,))

    assert (await feedback(app_conn, enricher_pool))[edge] == {}
