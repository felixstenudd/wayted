"""Small OSM fixtures written straight into raw, so the triggers queue them as in real use."""

from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg.types.json import Jsonb

type Conn = AsyncConnection[TupleRow]
# (node id, x, y) on a grid
type Point = tuple[int, int, int]
# (way_id, source, target, occurrence, forward, backward)
type Edge = tuple[int, int, int, int, list[str], list[str]]

# One grid step is 0.001 degrees: about 57 m east-west and 111 m north-south here.
ORIGIN_LON = 18.0
ORIGIN_LAT = 59.3
STEP = 0.001


async def add_node(conn: Conn, node_id: int, x: int, y: int) -> None:
    """Add a node at grid position (x, y), or move it there."""
    await conn.execute(
        """
        INSERT INTO raw.osm_nodes AS existing (id, tags, geom)
        VALUES (%s, '{}', ST_Point(%s, %s, 4326))
        ON CONFLICT (id) DO UPDATE SET geom = EXCLUDED.geom
        WHERE existing.geom IS DISTINCT FROM EXCLUDED.geom
        """,
        (node_id, ORIGIN_LON + x * STEP, ORIGIN_LAT + y * STEP),
    )


async def add_way(conn: Conn, way_id: int, node_ids: list[int], tags: dict[str, str]) -> None:
    """Add a way over existing nodes, or change it."""
    await conn.execute(
        """
        INSERT INTO raw.osm_ways AS existing (id, tags, node_ids) VALUES (%s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET tags = EXCLUDED.tags, node_ids = EXCLUDED.node_ids
        WHERE (existing.tags, existing.node_ids)
            IS DISTINCT FROM (EXCLUDED.tags, EXCLUDED.node_ids)
        """,
        (way_id, Jsonb(tags), node_ids),
    )


async def add_line(conn: Conn, way_id: int, points: list[Point], tags: dict[str, str]) -> None:
    """Add the nodes and a way through them in order."""
    for node_id, x, y in points:
        await add_node(conn, node_id, x, y)
    await add_way(conn, way_id, [node_id for node_id, _, _ in points], tags)


async def graph_edges(conn: Conn) -> list[Edge]:
    cur = await conn.execute(
        """
        SELECT way_id, source, target, occurrence, forward, backward FROM graph.edges
        ORDER BY way_id, source, target, occurrence
        """
    )
    return await cur.fetchall()


async def edge_ids(conn: Conn) -> dict[tuple[int, int, int, int], int]:
    """Edge ids by natural key (way_id, source, target, occurrence)."""
    cur = await conn.execute("SELECT way_id, source, target, occurrence, id FROM graph.edges")
    return {
        (way_id, source, target, occ): id_
        for way_id, source, target, occ, id_ in await cur.fetchall()
    }


async def pending_edges(conn: Conn) -> set[int]:
    cur = await conn.execute("SELECT edge_id FROM graph.pending_edges")
    return {edge_id for (edge_id,) in await cur.fetchall()}
