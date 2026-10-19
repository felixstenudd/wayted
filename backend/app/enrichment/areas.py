"""
Reads the area features inside a bounding box, for drawing them on a map.
"""

from dataclasses import dataclass
from typing import Any, Literal

from psycopg import AsyncConnection
from psycopg.rows import TupleRow

from app.sources.tiles import Bounds

# Seven decimals is what OSM stores.
AREAS_IN_BOUNDS = """
    SELECT layer, osm_type, osm_id, tags, ST_AsGeoJSON(geom, 7)::jsonb
    FROM enrich.areas
    WHERE ST_Intersects(geom, ST_MakeEnvelope(%(west)s, %(south)s, %(east)s, %(north)s, 4326))
    ORDER BY layer, osm_type, osm_id
"""


@dataclass(frozen=True, slots=True)
class Area:
    layer: str
    osm_type: Literal["way", "relation"]
    osm_id: int
    tags: dict[str, str]
    # GeoJSON MultiPolygon
    geometry: dict[str, Any]


async def areas_in_bounds(conn: AsyncConnection[TupleRow], bounds: Bounds) -> list[Area]:
    """
    Return every area that intersects bounds, whole. Raises ValueError when bounds are inside
    out.
    """
    if bounds.west > bounds.east:
        raise ValueError("West must not be east of east.")
    if bounds.south > bounds.north:
        raise ValueError("South must not be north of north.")
    cur = await conn.execute(
        AREAS_IN_BOUNDS,
        {"west": bounds.west, "south": bounds.south, "east": bounds.east, "north": bounds.north},
    )
    return [Area(*row) for row in await cur.fetchall()]
