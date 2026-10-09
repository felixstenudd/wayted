import pytest
from psycopg_pool import AsyncConnectionPool

from app.graph import map_pending

from .raw_data import Conn, add_line, add_node, add_way, graph_edges

pytestmark = pytest.mark.db

Pool = AsyncConnectionPool[Conn]
BOTH = ["cycling", "running"]
RESIDENTIAL = {"highway": "residential"}


async def test_crossing_ways_split_at_the_shared_node(admin_conn: Conn, mapper_pool: Pool) -> None:
    await add_line(admin_conn, 1, [(1, 0, 1), (2, 1, 1), (3, 2, 1)], RESIDENTIAL)
    await add_line(admin_conn, 2, [(4, 1, 0), (2, 1, 1), (5, 1, 2)], RESIDENTIAL)

    await map_pending(mapper_pool.connection)

    assert await graph_edges(admin_conn) == [
        (1, 1, 2, 1, BOTH, BOTH),
        (1, 2, 3, 1, BOTH, BOTH),
        (2, 2, 5, 1, BOTH, BOTH),
        (2, 4, 2, 1, BOTH, BOTH),
    ]


async def test_unshared_nodes_stay_inside_one_edge(admin_conn: Conn, mapper_pool: Pool) -> None:
    await add_line(admin_conn, 1, [(1, 0, 0), (2, 1, 0), (3, 2, 0)], RESIDENTIAL)

    await map_pending(mapper_pool.connection)

    cur = await admin_conn.execute(
        "SELECT source, target, ST_NPoints(geom), round(length_m) FROM graph.edges"
    )
    assert await cur.fetchall() == [(1, 3, 3, 114)]


async def test_t_junction_splits_only_the_through_way(admin_conn: Conn, mapper_pool: Pool) -> None:
    await add_line(admin_conn, 1, [(1, 0, 0), (2, 1, 0), (3, 2, 0)], RESIDENTIAL)
    await add_line(admin_conn, 2, [(2, 1, 0), (4, 1, 1)], RESIDENTIAL)

    await map_pending(mapper_pool.connection)

    assert [e[:3] for e in await graph_edges(admin_conn)] == [(1, 1, 2), (1, 2, 3), (2, 2, 4)]


async def test_self_crossing_way_splits_where_it_crosses(
    admin_conn: Conn, mapper_pool: Pool
) -> None:
    # A figure six: 1 → 2 → 3 → 4 → back to 2 → 5
    for node_id, x, y in [(1, 0, 0), (2, 1, 0), (3, 2, 0), (4, 2, 1), (5, 1, 1)]:
        await add_node(admin_conn, node_id, x, y)
    await add_way(admin_conn, 1, [1, 2, 3, 4, 2, 5], RESIDENTIAL)

    await map_pending(mapper_pool.connection)

    assert [e[:4] for e in await graph_edges(admin_conn)] == [
        (1, 1, 2, 1),
        (1, 2, 2, 1),
        (1, 2, 5, 1),
    ]


async def test_repeated_node_pair_gets_a_second_occurrence(
    admin_conn: Conn, mapper_pool: Pool
) -> None:
    # 1 → 2 → 3 → 1 → 2 runs from 1 to 2 twice.
    for node_id, x, y in [(1, 0, 0), (2, 1, 0), (3, 1, 1)]:
        await add_node(admin_conn, node_id, x, y)
    await add_way(admin_conn, 1, [1, 2, 3, 1, 2], RESIDENTIAL)

    await map_pending(mapper_pool.connection)

    assert [e[:4] for e in await graph_edges(admin_conn)] == [
        (1, 1, 2, 1),
        (1, 1, 2, 2),
        (1, 2, 1, 1),
    ]


async def test_closed_way_becomes_a_loop(admin_conn: Conn, mapper_pool: Pool) -> None:
    for node_id, x, y in [(1, 0, 0), (2, 1, 0), (3, 1, 1)]:
        await add_node(admin_conn, node_id, x, y)
    await add_way(admin_conn, 1, [1, 2, 3, 1], RESIDENTIAL)

    await map_pending(mapper_pool.connection)

    assert [e[:4] for e in await graph_edges(admin_conn)] == [(1, 1, 1, 1)]


async def test_unroutable_ways_do_not_split_routable_ones(
    admin_conn: Conn, mapper_pool: Pool
) -> None:
    await add_line(admin_conn, 1, [(1, 0, 0), (2, 1, 0), (3, 2, 0)], RESIDENTIAL)
    await add_line(admin_conn, 2, [(2, 1, 0), (4, 1, 1)], {"highway": "motorway"})
    await add_line(admin_conn, 3, [(2, 1, 0), (5, 1, -1)], {"building": "yes"})

    await map_pending(mapper_pool.connection)

    assert [e[:3] for e in await graph_edges(admin_conn)] == [(1, 1, 3)]


async def test_way_with_a_missing_node_is_skipped(admin_conn: Conn, mapper_pool: Pool) -> None:
    await add_line(admin_conn, 1, [(1, 0, 0), (2, 1, 0)], RESIDENTIAL)
    await add_way(admin_conn, 2, [2, 99], RESIDENTIAL)

    result = await map_pending(mapper_pool.connection)

    assert [e[:3] for e in await graph_edges(admin_conn)] == [(1, 1, 2)]
    assert result.batches[0].ways_skipped == 1


async def test_node_repeated_back_to_back_is_not_a_split(
    admin_conn: Conn, mapper_pool: Pool
) -> None:
    for node_id, x, y in [(1, 0, 0), (2, 1, 0), (3, 2, 0)]:
        await add_node(admin_conn, node_id, x, y)
    await add_way(admin_conn, 1, [1, 2, 2, 3], RESIDENTIAL)

    await map_pending(mapper_pool.connection)

    cur = await admin_conn.execute("SELECT source, target, ST_NPoints(geom) FROM graph.edges")
    assert await cur.fetchall() == [(1, 3, 3)]


async def test_way_with_one_distinct_node_is_skipped(admin_conn: Conn, mapper_pool: Pool) -> None:
    await add_node(admin_conn, 1, 0, 0)
    await add_way(admin_conn, 1, [1, 1], RESIDENTIAL)

    result = await map_pending(mapper_pool.connection)

    assert await graph_edges(admin_conn) == []
    assert result.batches[0].ways_skipped == 1


async def test_vertices_are_the_edge_ends(admin_conn: Conn, mapper_pool: Pool) -> None:
    await add_line(admin_conn, 1, [(1, 0, 0), (2, 1, 0), (3, 2, 0)], RESIDENTIAL)

    await map_pending(mapper_pool.connection)

    cur = await admin_conn.execute("SELECT id FROM graph.vertices ORDER BY id")
    assert await cur.fetchall() == [(1,), (3,)]


async def test_empty_queue_does_nothing(mapper_pool: Pool) -> None:
    result = await map_pending(mapper_pool.connection)

    assert result.batches == ()
