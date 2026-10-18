"""Area fixtures written straight into raw, and readers for what the enricher built."""

from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from app.enrichment import EnrichResult, enrich_pending
from app.graph import map_pending

from ..graph.raw_data import ORIGIN_LAT, ORIGIN_LON, STEP, Conn, Point, add_line, add_node, add_way

type Pool = AsyncConnectionPool[Conn]
# (x0, y0, x1, y1) on the raw_data grid
type Box = tuple[int, int, int, int]


async def add_square(
    conn: Conn, way_id: int, first_node: int, box: Box, tags: dict[str, str]
) -> None:
    """A closed way around box, over nodes first_node to first_node + 3."""
    x0, y0, x1, y1 = box
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for offset, (x, y) in enumerate(corners):
        await add_node(conn, first_node + offset, x, y)
    nodes = [first_node + offset for offset in range(4)]
    await add_way(conn, way_id, [*nodes, first_node], tags)


async def add_relation(
    conn: Conn, relation_id: int, ways: list[tuple[int, str]], tags: dict[str, str]
) -> None:
    """A relation over (way id, role) members, or change it."""
    members = [{"type": "way", "ref": way_id, "role": role} for way_id, role in ways]
    await conn.execute(
        """
        INSERT INTO raw.osm_relations AS existing (id, tags, members) VALUES (%s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET tags = EXCLUDED.tags, members = EXCLUDED.members
        WHERE (existing.tags, existing.members) IS DISTINCT FROM (EXCLUDED.tags, EXCLUDED.members)
        """,
        (relation_id, Jsonb(tags), Jsonb(members)),
    )


async def add_road(conn: Conn, way_id: int, a: Point, b: Point) -> None:
    """A highway=path from a to b, one edge once mapped."""
    await add_line(conn, way_id, [a, b], {"highway": "path"})


def grid_wkt(outer: Box, *holes: Box) -> str:
    """WKT of a polygon on the grid, for comparing with ST_Equals."""

    def ring(box: Box) -> str:
        x0, y0, x1, y1 = box
        corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
        return ", ".join(f"{ORIGIN_LON + x * STEP} {ORIGIN_LAT + y * STEP}" for x, y in corners)

    return "POLYGON(" + ", ".join(f"({ring(box)})" for box in (outer, *holes)) + ")"


async def run(mapper_pool: Pool, enricher_pool: Pool) -> EnrichResult:
    await map_pending(mapper_pool.connection)
    return await enrich_pending(enricher_pool.connection)


async def areas(conn: Conn) -> list[tuple[str, int]]:
    """(osm_type, osm_id) of every row in enrich.areas, sorted."""
    cur = await conn.execute("SELECT osm_type, osm_id FROM enrich.areas ORDER BY osm_type, osm_id")
    return [(osm_type, osm_id) for osm_type, osm_id in await cur.fetchall()]


async def area_is(conn: Conn, osm_type: str, osm_id: int, wkt: str) -> bool:
    """Whether the feature's geometry is topologically equal to wkt."""
    cur = await conn.execute(
        """
        SELECT ST_Equals(geom, ST_GeomFromText(%s, 4326)) FROM enrich.areas
        WHERE osm_type = %s AND osm_id = %s
        """,
        (wkt, osm_type, osm_id),
    )
    row = await cur.fetchone()
    return row is not None and bool(row[0])


async def feature_ways(conn: Conn) -> set[tuple[str, int, int]]:
    """Every row of enrich.feature_ways."""
    cur = await conn.execute("SELECT osm_type, osm_id, way_id FROM enrich.feature_ways")
    return {(osm_type, osm_id, way_id) for osm_type, osm_id, way_id in await cur.fetchall()}
