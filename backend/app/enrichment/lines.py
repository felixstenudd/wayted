"""
Reads the line features inside a bounding box, for drawing them on a map.
"""

from dataclasses import dataclass
from typing import Any, Literal

from psycopg import AsyncConnection
from psycopg.rows import TupleRow

from app.sources.tiles import Bounds

from .areas import check_bounds

LINES_IN_BOUNDS = """
    SELECT layer, osm_type, osm_id, tags, ST_AsGeoJSON(geom, 7)::jsonb
    FROM enrich.lines
    WHERE ST_Intersects(geom, ST_MakeEnvelope(%(west)s, %(south)s, %(east)s, %(north)s, 4326))
    ORDER BY layer, osm_type, osm_id
"""


@dataclass(frozen=True, slots=True)
class Line:
    layer: str
    osm_type: Literal["way"]
    osm_id: int
    tags: dict[str, str]
    # GeoJSON MultiLineString
    geometry: dict[str, Any]


async def lines_in_bounds(conn: AsyncConnection[TupleRow], bounds: Bounds) -> list[Line]:
    """
    Return every line that intersects bounds, whole. Raises ValueError when bounds are inside
    out.
    """
    check_bounds(bounds)
    cur = await conn.execute(
        LINES_IN_BOUNDS,
        {"west": bounds.west, "south": bounds.south, "east": bounds.east, "north": bounds.north},
    )
    return [Line(*row) for row in await cur.fetchall()]
