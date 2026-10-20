from uuid import UUID

import pytest
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from app.routing.attributes import KEYS

from .app_data import add_edges, add_segment_review, add_user

pytestmark = pytest.mark.db

type Conn = AsyncConnection[TupleRow]
type Pool = AsyncConnectionPool[Conn]

LINE = "SRID=4326;LINESTRING(20 63.8, 20.002 63.8)"


async def add_route(conn: Conn, user_id: UUID) -> int:
    cur = await conn.execute(
        """
        INSERT INTO app.routes
            (user_id, name, activity, shape, target_distance_m, geom, distance_m)
        VALUES (%s, 'Morning loop', 'running', 'loop', 5000, %s, 100)
        RETURNING id
        """,
        (user_id, LINE),
    )
    row = await cur.fetchone()
    assert row is not None
    route_id: int = row[0]
    return route_id


async def queued_edges(conn: Conn) -> set[int]:
    cur = await conn.execute("SELECT edge_id FROM graph.pending_edges")
    return {row[0] for row in await cur.fetchall()}


async def test_ref_attributes_match_the_route_attributes(app_conn: Conn) -> None:
    cur = await app_conn.execute("SELECT key FROM ref.attributes")

    assert {row[0] for row in await cur.fetchall()} == KEYS


async def test_attribute_reasons_have_a_good_and_a_bad_side(app_conn: Conn) -> None:
    cur = await app_conn.execute(
        """
        SELECT topic, array_agg(sentiment ORDER BY sentiment)
        FROM ref.review_reasons WHERE attribute IS NOT NULL GROUP BY topic
        """
    )

    assert all(sentiments == [-1, 1] for _, sentiments in await cur.fetchall())


async def test_a_new_segment_review_queues_its_edges_still_in_the_graph(
    app_conn: Conn, api_pool: Pool
) -> None:
    user_id = await add_user(app_conn)
    edges = await add_edges(app_conn, 3)
    stale_edge = 999

    async with api_pool.connection() as conn:
        await add_segment_review(
            conn, user_id, None, [edges[0], edges[1], stale_edge], ["green_bad"]
        )

    assert await queued_edges(app_conn) == {edges[0], edges[1]}


async def test_changing_the_reasons_queues_the_reviews_edges(
    app_conn: Conn, api_pool: Pool
) -> None:
    user_id = await add_user(app_conn)
    edges = await add_edges(app_conn, 3)
    review_id = await add_segment_review(app_conn, user_id, None, [edges[2]], ["green_bad"])
    await app_conn.execute("TRUNCATE graph.pending_edges")

    async with api_pool.connection() as conn:
        await conn.execute(
            "DELETE FROM app.segment_review_reasons WHERE review_id = %s", (review_id,)
        )
        await conn.execute(
            "INSERT INTO app.segment_review_reasons (review_id, reason) VALUES (%s, 'green_good')",
            (review_id,),
        )

    assert await queued_edges(app_conn) == {edges[2]}


async def test_deleting_a_review_queues_its_edges(app_conn: Conn, api_pool: Pool) -> None:
    user_id = await add_user(app_conn)
    edges = await add_edges(app_conn, 2)
    review_id = await add_segment_review(app_conn, user_id, None, edges, ["access_bad"])
    await app_conn.execute("TRUNCATE graph.pending_edges")

    async with api_pool.connection() as conn:
        await conn.execute("DELETE FROM app.segment_reviews WHERE id = %s", (review_id,))

    assert await queued_edges(app_conn) == set(edges)


async def test_deleting_a_user_queues_the_edges_of_their_reviews(app_conn: Conn) -> None:
    user_id = await add_user(app_conn)
    edges = await add_edges(app_conn, 2)
    await add_segment_review(app_conn, user_id, None, edges, ["safety_bad"])
    await app_conn.execute("TRUNCATE graph.pending_edges")

    await app_conn.execute("DELETE FROM app.users WHERE id = %s", (user_id,))

    assert await queued_edges(app_conn) == set(edges)


async def test_segment_reviews_outlive_their_route(app_conn: Conn, api_pool: Pool) -> None:
    user_id = await add_user(app_conn)
    edges = await add_edges(app_conn, 1)
    route_id = await add_route(app_conn, user_id)
    review_id = await add_segment_review(app_conn, user_id, route_id, edges, ["water_good"])

    async with api_pool.connection() as conn:
        await conn.execute("DELETE FROM app.routes WHERE id = %s", (route_id,))

    cur = await app_conn.execute(
        "SELECT route_id FROM app.segment_reviews WHERE id = %s", (review_id,)
    )
    assert await cur.fetchone() == (None,)


async def test_route_reviews_go_with_their_route(app_conn: Conn, api_pool: Pool) -> None:
    user_id = await add_user(app_conn)
    route_id = await add_route(app_conn, user_id)
    await app_conn.execute(
        "INSERT INTO app.route_reviews (user_id, route_id) VALUES (%s, %s)", (user_id, route_id)
    )
    await app_conn.execute(
        """
        INSERT INTO app.route_review_answers (user_id, route_id, attribute, answer)
        VALUES (%s, %s, 'green', 1)
        """,
        (user_id, route_id),
    )

    async with api_pool.connection() as conn:
        await conn.execute("DELETE FROM app.routes WHERE id = %s", (route_id,))

    cur = await app_conn.execute(
        """
        SELECT (SELECT count(*) FROM app.route_reviews),
               (SELECT count(*) FROM app.route_review_answers)
        """
    )
    assert await cur.fetchone() == (0, 0)
