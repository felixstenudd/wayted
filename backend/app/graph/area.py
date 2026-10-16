"""
Reads the part of the graph inside a bounding box, for drawing it on a map.
"""

from dataclasses import dataclass
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import TupleRow

from app.sources.tiles import Bounds

# Seven decimals is what OSM stores.
EDGES_IN_BOUNDS = """
    SELECT edge.id, edge.way_id, edge.source, edge.target, edge.length_m, edge.forward,
           edge.backward, edge.scores, way.tags, ST_AsGeoJSON(edge.geom, 7)::jsonb
    FROM graph.edges AS edge
    JOIN graph.ways AS way ON way.id = edge.way_id
    WHERE ST_Intersects(
        edge.geom, ST_MakeEnvelope(%(west)s, %(south)s, %(east)s, %(north)s, 4326)
    )
    LIMIT %(limit)s
"""

VERTICES = """
    SELECT id, ST_AsGeoJSON(geom, 7)::jsonb FROM graph.vertices WHERE id = ANY(%s) ORDER BY id
"""


class AreaTooLarge(Exception):
    """The bounds hold more edges than the caller allows."""


@dataclass(frozen=True, slots=True)
class AreaEdge:
    id: int
    way_id: int
    source: int
    target: int
    length_m: float
    forward: list[str]
    backward: list[str]
    scores: dict[str, Any]
    # of the edge's way
    tags: dict[str, str]
    # GeoJSON LineString
    geometry: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AreaVertex:
    id: int
    # GeoJSON Point
    geometry: dict[str, Any]


@dataclass(frozen=True, slots=True)
class GraphArea:
    edges: list[AreaEdge]
    vertices: list[AreaVertex]


async def graph_in_bounds(
    conn: AsyncConnection[TupleRow], bounds: Bounds, max_edges: int
) -> GraphArea:
    """
    Return the edges that intersect bounds and the vertices at their ends. An edge that crosses
    the border comes whole, with both vertices.

    Raises AreaTooLarge when bounds hold more than max_edges edges, and ValueError when
    bounds are inside out.
    """
    if bounds.west > bounds.east:
        raise ValueError("West must not be east of east.")
    if bounds.south > bounds.north:
        raise ValueError("South must not be north of north.")
    cur = await conn.execute(
        EDGES_IN_BOUNDS,
        {
            "west": bounds.west,
            "south": bounds.south,
            "east": bounds.east,
            "north": bounds.north,
            "limit": max_edges + 1,
        },
    )
    edges = sorted((AreaEdge(*row) for row in await cur.fetchall()), key=lambda edge: edge.id)
    if len(edges) > max_edges:
        raise AreaTooLarge(f"The area holds more than {max_edges} edges.")
    ends = sorted({end for edge in edges for end in (edge.source, edge.target)})
    cur = await conn.execute(VERTICES, (ends,))
    return GraphArea(edges, [AreaVertex(*row) for row in await cur.fetchall()])
