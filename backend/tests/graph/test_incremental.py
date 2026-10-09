import pytest
from psycopg_pool import AsyncConnectionPool

from app.graph import map_pending

from .raw_data import Conn, add_line, add_node, add_way, edge_ids, graph_edges, pending_edges

pytestmark = pytest.mark.db

Pool = AsyncConnectionPool[Conn]
BOTH = ["cycling", "running"]
RESIDENTIAL = {"highway": "residential"}


async def forget_scoring_work(conn: Conn) -> None:
    """Score every edge and empty the enricher's queue, as if the enricher had run."""
    await conn.execute("""UPDATE graph.edges SET scores = '{"green": 0.5}'""")
    await conn.execute("TRUNCATE graph.pending_edges")


async def test_new_edges_are_queued_for_the_enricher(admin_conn: Conn, mapper_pool: Pool) -> None:
    await add_line(admin_conn, 1, [(1, 0, 0), (2, 1, 0)], RESIDENTIAL)

    await map_pending(mapper_pool.connection)

    assert await pending_edges(admin_conn) == set((await edge_ids(admin_conn)).values())


async def test_unchanged_reimport_keeps_edge_ids(admin_conn: Conn, mapper_pool: Pool) -> None:
    await add_line(admin_conn, 1, [(1, 0, 1), (2, 1, 1), (3, 2, 1)], RESIDENTIAL)
    await add_line(admin_conn, 2, [(4, 1, 0), (2, 1, 1), (5, 1, 2)], RESIDENTIAL)
    await map_pending(mapper_pool.connection)
    await forget_scoring_work(admin_conn)
    before = await edge_ids(admin_conn)

    await admin_conn.execute("INSERT INTO graph.pending_ways (way_id) SELECT id FROM raw.osm_ways")
    result = await map_pending(mapper_pool.connection)

    assert await edge_ids(admin_conn) == before
    assert await pending_edges(admin_conn) == set()
    batch = result.batches[0]
    assert (batch.edges_inserted, batch.edges_updated, batch.edges_deleted) == (0, 0, 0)


async def test_moved_node_updates_the_edge_and_clears_its_scores(
    admin_conn: Conn, mapper_pool: Pool
) -> None:
    await add_line(admin_conn, 1, [(1, 0, 0), (2, 1, 0), (3, 2, 0)], RESIDENTIAL)
    await map_pending(mapper_pool.connection)
    await forget_scoring_work(admin_conn)
    [edge_id] = (await edge_ids(admin_conn)).values()

    await add_node(admin_conn, 2, 1, 1)
    await map_pending(mapper_pool.connection)

    cur = await admin_conn.execute(
        "SELECT id, ST_NPoints(geom), round(length_m), scores FROM graph.edges"
    )
    assert await cur.fetchall() == [(edge_id, 3, 250, {})]
    assert await pending_edges(admin_conn) == {edge_id}


async def test_moved_shared_node_updates_every_way_through_it(
    admin_conn: Conn, mapper_pool: Pool
) -> None:
    await add_line(admin_conn, 1, [(1, 0, 0), (2, 1, 0), (3, 2, 0)], RESIDENTIAL)
    await add_line(admin_conn, 2, [(2, 1, 0), (4, 1, 1)], RESIDENTIAL)
    await map_pending(mapper_pool.connection)
    await forget_scoring_work(admin_conn)

    await add_node(admin_conn, 2, 1, -1)
    result = await map_pending(mapper_pool.connection)

    assert result.batches[0].edges_updated == 3
    assert await pending_edges(admin_conn) == set((await edge_ids(admin_conn)).values())
    cur = await admin_conn.execute(
        """
        SELECT count(*) FROM graph.edges e JOIN graph.vertices v ON v.id = 2
        WHERE ST_Intersects(e.geom, v.geom)
        """
    )
    assert await cur.fetchone() == (3,)


async def test_queued_way_missing_from_raw_changes_nothing(
    admin_conn: Conn, mapper_pool: Pool
) -> None:
    await add_line(admin_conn, 1, [(1, 0, 0), (2, 1, 0)], RESIDENTIAL)
    await map_pending(mapper_pool.connection)
    before = await edge_ids(admin_conn)

    await admin_conn.execute("INSERT INTO graph.pending_ways (way_id) VALUES (999)")
    result = await map_pending(mapper_pool.connection)

    assert result.batches[0].ways_claimed == 1
    assert await edge_ids(admin_conn) == before


async def test_change_committed_during_a_batch_is_mapped_next_run(
    admin_conn: Conn, mapper_pool: Pool, downloader_pool: Pool
) -> None:
    await add_line(admin_conn, 1, [(1, 0, 0), (2, 1, 0)], RESIDENTIAL)

    # A download changes the way while it is still queued, and commits while a batch maps it.
    async with downloader_pool.connection() as conn, conn.transaction():
        await add_node(conn, 3, 2, 0)
        await add_way(conn, 1, [1, 2, 3], RESIDENTIAL)
        await map_pending(mapper_pool.connection)
    await map_pending(mapper_pool.connection)

    assert [e[:3] for e in await graph_edges(admin_conn)] == [(1, 1, 3)]


async def test_each_changed_edge_is_queued_once(admin_conn: Conn, mapper_pool: Pool) -> None:
    await add_line(admin_conn, 1, [(1, 0, 0), (2, 1, 0)], RESIDENTIAL)
    await map_pending(mapper_pool.connection)
    await forget_scoring_work(admin_conn)

    # Retagged and extended: the old edge goes, a new one takes its place.
    await add_node(admin_conn, 3, 2, 0)
    await add_way(admin_conn, 1, [1, 2, 3], {"highway": "residential", "oneway": "yes"})
    await map_pending(mapper_pool.connection)

    [edge_id] = (await edge_ids(admin_conn)).values()
    cur = await admin_conn.execute("SELECT edge_id FROM graph.pending_edges")
    assert await cur.fetchall() == [(edge_id,)]


async def test_way_moved_off_a_shared_node_lets_the_neighbour_merge(
    admin_conn: Conn, mapper_pool: Pool
) -> None:
    await add_line(admin_conn, 1, [(1, 0, 0), (2, 1, 0), (3, 2, 0)], RESIDENTIAL)
    await add_line(admin_conn, 2, [(2, 1, 0), (4, 1, 1)], RESIDENTIAL)
    await map_pending(mapper_pool.connection)

    await add_node(admin_conn, 5, 0, 1)
    await add_way(admin_conn, 2, [5, 4], RESIDENTIAL)
    await map_pending(mapper_pool.connection)

    assert [e[:3] for e in await graph_edges(admin_conn)] == [(1, 1, 3), (2, 5, 4)]


async def test_split_left_by_an_earlier_batch_is_merged_later(
    admin_conn: Conn, mapper_pool: Pool
) -> None:
    await add_line(admin_conn, 1, [(1, 0, 0), (2, 1, 0), (3, 2, 0)], RESIDENTIAL)
    await add_line(admin_conn, 2, [(4, 1, 1), (5, 2, 1)], RESIDENTIAL)
    await add_line(admin_conn, 3, [(2, 1, 0), (4, 1, 1)], RESIDENTIAL)
    await map_pending(mapper_pool.connection)

    # Way 2 is claimed first and rebuilds its neighbour, way 3, which has meanwhile moved off
    # node 2. Way 3's own claim in the next batch then no longer sees node 2.
    await add_way(admin_conn, 2, [4, 5], {"highway": "residential", "name": "Ny gata"})
    await add_node(admin_conn, 6, 0, 1)
    await add_way(admin_conn, 3, [6, 4], RESIDENTIAL)
    await map_pending(mapper_pool.connection, batch_size=1)

    assert [e[:3] for e in await graph_edges(admin_conn)] == [(1, 1, 3), (2, 4, 5), (3, 6, 4)]


async def test_moved_end_node_moves_the_vertex(admin_conn: Conn, mapper_pool: Pool) -> None:
    await add_line(admin_conn, 1, [(1, 0, 0), (2, 1, 0)], RESIDENTIAL)
    await map_pending(mapper_pool.connection)

    await add_node(admin_conn, 2, 2, 0)
    await map_pending(mapper_pool.connection)

    cur = await admin_conn.execute(
        "SELECT v.geom = n.geom FROM graph.vertices v JOIN raw.osm_nodes n USING (id) WHERE id = 2"
    )
    assert await cur.fetchone() == (True,)


async def test_retagged_way_updates_access_and_clears_scores(
    admin_conn: Conn, mapper_pool: Pool
) -> None:
    await add_line(admin_conn, 1, [(1, 0, 0), (2, 1, 0)], RESIDENTIAL)
    await map_pending(mapper_pool.connection)
    await forget_scoring_work(admin_conn)
    [edge_id] = (await edge_ids(admin_conn)).values()
    one_way = {"highway": "residential", "oneway": "yes"}

    await add_way(admin_conn, 1, [1, 2], one_way)
    await map_pending(mapper_pool.connection)

    cur = await admin_conn.execute("SELECT id, forward, backward, scores FROM graph.edges")
    assert await cur.fetchall() == [(edge_id, BOTH, ["running"], {})]
    cur = await admin_conn.execute("SELECT tags FROM graph.ways")
    assert await cur.fetchall() == [(one_way,)]
    assert await pending_edges(admin_conn) == {edge_id}


async def test_new_way_splits_a_mapped_neighbour(admin_conn: Conn, mapper_pool: Pool) -> None:
    await add_line(admin_conn, 1, [(1, 0, 0), (2, 1, 0), (3, 2, 0)], RESIDENTIAL)
    await map_pending(mapper_pool.connection)

    await add_line(admin_conn, 2, [(2, 1, 0), (4, 1, 1)], RESIDENTIAL)
    result = await map_pending(mapper_pool.connection)

    assert [e[:3] for e in await graph_edges(admin_conn)] == [(1, 1, 2), (1, 2, 3), (2, 2, 4)]
    batch = result.batches[0]
    assert (batch.edges_inserted, batch.edges_deleted) == (3, 1)


async def test_way_turned_unroutable_leaves_and_its_neighbour_merges(
    admin_conn: Conn, mapper_pool: Pool
) -> None:
    await add_line(admin_conn, 1, [(1, 0, 0), (2, 1, 0), (3, 2, 0)], RESIDENTIAL)
    await add_line(admin_conn, 2, [(2, 1, 0), (4, 1, 1)], RESIDENTIAL)
    await map_pending(mapper_pool.connection)

    await add_way(admin_conn, 2, [2, 4], {"highway": "construction"})
    await map_pending(mapper_pool.connection)

    assert [e[:3] for e in await graph_edges(admin_conn)] == [(1, 1, 3)]
    cur = await admin_conn.execute(
        """
        SELECT (SELECT array_agg(id ORDER BY id) FROM graph.ways),
               (SELECT array_agg(id ORDER BY id) FROM graph.vertices)
        """
    )
    assert await cur.fetchone() == ([1], [1, 3])


async def test_way_deleted_from_raw_leaves_the_graph(admin_conn: Conn, mapper_pool: Pool) -> None:
    await add_line(admin_conn, 1, [(1, 0, 0), (2, 1, 0)], RESIDENTIAL)
    await map_pending(mapper_pool.connection)

    await admin_conn.execute("DELETE FROM raw.osm_ways")
    await map_pending(mapper_pool.connection)

    cur = await admin_conn.execute(
        """
        SELECT (SELECT count(*) FROM graph.edges), (SELECT count(*) FROM graph.vertices),
               (SELECT count(*) FROM graph.ways)
        """
    )
    assert await cur.fetchone() == (0, 0, 0)
