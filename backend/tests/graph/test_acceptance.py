import psycopg
import pytest
from psycopg_pool import AsyncConnectionPool

from app.graph import map_pending, queries

from .raw_data import Conn, Point, add_line

pytestmark = pytest.mark.db

Pool = AsyncConnectionPool[Conn]
RESIDENTIAL = {"highway": "residential"}
type Tile = list[tuple[int, list[Point]]]

# Two tiles meeting at node 3 on their border (x = 2).
WEST: Tile = [(10, [(1, 0, 0), (2, 1, 0), (3, 2, 0)]), (11, [(4, 1, 1), (2, 1, 0)])]
EAST: Tile = [(20, [(3, 2, 0), (5, 3, 0), (6, 4, 0)]), (21, [(5, 3, 0), (7, 3, 1)])]


async def import_tile(conn: Conn, pool: Pool, tile: Tile) -> None:
    for way_id, points in tile:
        await add_line(conn, way_id, points, RESIDENTIAL)
    await map_pending(pool)


async def graph_snapshot(conn: Conn) -> list[tuple[object, ...]]:
    cur = await conn.execute(
        """
        SELECT way_id, source, target, occurrence, forward, backward, ST_AsText(geom)
        FROM graph.edges ORDER BY way_id, source, target, occurrence
        """
    )
    return await cur.fetchall()


async def clear_all(conn: Conn) -> None:
    await conn.execute(
        """
        TRUNCATE raw.osm_nodes, raw.osm_ways, graph.ways, graph.vertices, graph.edges,
            graph.pending_ways, graph.pending_nodes, graph.pending_edges
        """
    )


@pytest.mark.parametrize("east_first", [False, True])
async def test_adjacent_tiles_give_the_same_graph_in_either_order(
    admin_conn: Conn, mapper_pool: Pool, east_first: bool
) -> None:
    await import_tile(admin_conn, mapper_pool, WEST + EAST)
    together = await graph_snapshot(admin_conn)
    await clear_all(admin_conn)

    for tile in (EAST, WEST) if east_first else (WEST, EAST):
        await import_tile(admin_conn, mapper_pool, tile)

    assert await graph_snapshot(admin_conn) == together


async def test_batches_of_one_way_give_the_same_graph(admin_conn: Conn, mapper_pool: Pool) -> None:
    await import_tile(admin_conn, mapper_pool, WEST + EAST)
    together = await graph_snapshot(admin_conn)
    await admin_conn.execute(
        "TRUNCATE graph.ways, graph.vertices, graph.edges, graph.pending_edges"
    )
    await admin_conn.execute("INSERT INTO graph.pending_ways (way_id) SELECT id FROM raw.osm_ways")

    result = await map_pending(mapper_pool, batch_size=1)

    assert len(result.batches) == 4
    assert await graph_snapshot(admin_conn) == together


async def test_failed_batch_leaves_graph_and_queue_untouched(
    admin_conn: Conn, mapper_pool: Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    await import_tile(admin_conn, mapper_pool, WEST)
    before = await graph_snapshot(admin_conn)
    await add_line(admin_conn, 20, EAST[0][1], RESIDENTIAL)
    # Runs after ways and vertices are written and stale edges deleted.
    monkeypatch.setattr(queries, "UPDATE_EDGES", "SELECT 1 / 0")

    with pytest.raises(psycopg.errors.DivisionByZero):
        await map_pending(mapper_pool)

    assert await graph_snapshot(admin_conn) == before
    cur = await admin_conn.execute(
        """
        SELECT (SELECT array_agg(way_id) FROM graph.pending_ways),
               (SELECT array_agg(id ORDER BY id) FROM graph.ways),
               (SELECT array_agg(id ORDER BY id) FROM graph.vertices)
        """
    )
    assert await cur.fetchone() == ([20], [10, 11], [1, 2, 3, 4])


async def test_pgr_dijkstra_routes_across_a_tile_border(
    admin_conn: Conn, mapper_pool: Pool
) -> None:
    await import_tile(admin_conn, mapper_pool, WEST)
    await import_tile(admin_conn, mapper_pool, EAST)

    cur = await admin_conn.execute(
        """
        SELECT array_agg(node ORDER BY path_seq) FROM pgr_dijkstra(
            'SELECT id, source, target, length_m AS cost, length_m AS reverse_cost
             FROM graph.edges',
            4, 7)
        """
    )
    assert await cur.fetchone() == ([4, 2, 3, 5, 7],)


@pytest.mark.parametrize(("activity", "found"), [("cycling", False), ("running", True)])
async def test_pgr_dijkstra_respects_one_way_per_activity(
    admin_conn: Conn, mapper_pool: Pool, activity: str, found: bool
) -> None:
    one_way = {"highway": "residential", "oneway": "yes"}
    await add_line(admin_conn, 1, [(1, 0, 0), (2, 1, 0)], one_way)
    await map_pending(mapper_pool)
    edges_sql = f"""
        SELECT id, source, target,
               CASE WHEN '{activity}' = ANY(forward) THEN length_m ELSE -1 END AS cost,
               CASE WHEN '{activity}' = ANY(backward) THEN length_m ELSE -1 END AS reverse_cost
        FROM graph.edges
    """

    cur = await admin_conn.execute("SELECT count(*) > 0 FROM pgr_dijkstra(%s, 2, 1)", (edges_sql,))

    assert await cur.fetchone() == (found,)
