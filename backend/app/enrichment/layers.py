"""Turn raw elements into feature geometry, one table per kind of geometry."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg.types.json import Jsonb

# Matching candidates, with their member ways in order and a polygon, or NULL when a member
# way or node is missing, the ways form no closed ring, or nothing is left after repair.
# ST_BuildArea nests rings by geometry, so outer and inner roles are not read.
BUILD_AREAS = """
    CREATE TEMP TABLE built_areas ON COMMIT DROP AS
    WITH matched AS (
        SELECT c.osm_type, c.osm_id, w.tags, ARRAY[w.id] AS way_ids
        FROM feature_candidates c JOIN raw.osm_ways w ON w.id = c.osm_id
        WHERE c.osm_type = 'way' AND w.tags @> ANY(%(match)s::jsonb[])
        UNION ALL
        SELECT c.osm_type, c.osm_id, r.tags,
               ARRAY(
                   SELECT (m.member ->> 'ref')::bigint
                   FROM jsonb_array_elements(r.members) WITH ORDINALITY AS m(member, ord)
                   WHERE m.member ->> 'type' = 'way'
                   ORDER BY m.ord
               )
        FROM feature_candidates c JOIN raw.osm_relations r ON r.id = c.osm_id
        WHERE c.osm_type = 'relation' AND r.tags ->> 'type' = 'multipolygon'
          AND r.tags @> ANY(%(match)s::jsonb[])
    ),
    lines AS (
        SELECT m.osm_type, m.osm_id,
               (
                   SELECT CASE WHEN count(n.id) = cardinality(w.node_ids)
                               THEN ST_MakeLine(n.geom ORDER BY p.ord) END
                   FROM unnest(w.node_ids) WITH ORDINALITY AS p(id, ord)
                   LEFT JOIN raw.osm_nodes n ON n.id = p.id
               ) AS line
        FROM matched m
        LEFT JOIN LATERAL unnest(m.way_ids) AS part(way_id) ON true
        LEFT JOIN raw.osm_ways w ON w.id = part.way_id
    ),
    shapes AS (
        SELECT osm_type, osm_id,
               CASE WHEN bool_and(line IS NOT NULL) THEN
                   ST_CollectionExtract(ST_MakeValid(ST_BuildArea(ST_Collect(line))), 3)
               END AS geom
        FROM lines
        GROUP BY osm_type, osm_id
    )
    SELECT m.osm_type, m.osm_id, m.tags, m.way_ids,
           CASE WHEN NOT ST_IsEmpty(s.geom) THEN ST_Multi(s.geom) END AS geom
    FROM matched m JOIN shapes s USING (osm_type, osm_id)
"""

WRITE_FEATURE_WAYS = """
    INSERT INTO enrich.feature_ways (osm_type, osm_id, way_id)
    SELECT osm_type, osm_id, unnest(way_ids) FROM built_areas
    ON CONFLICT DO NOTHING
"""

# Old geometry of candidates that lost or changed it, and new geometry that differs.
FIND_CHANGED_AREAS = """
    INSERT INTO changed_features (layer, geom)
    SELECT a.layer, a.geom
    FROM enrich.areas a
    JOIN feature_candidates c USING (osm_type, osm_id)
    LEFT JOIN built_areas b USING (osm_type, osm_id)
    WHERE a.layer = %(layer)s AND a.geom IS DISTINCT FROM b.geom
    UNION ALL
    SELECT %(layer)s, b.geom
    FROM built_areas b
    LEFT JOIN enrich.areas a
        ON (a.layer, a.osm_type, a.osm_id) = (%(layer)s, b.osm_type, b.osm_id)
    WHERE b.geom IS NOT NULL AND a.geom IS DISTINCT FROM b.geom
"""

DELETE_AREAS = """
    DELETE FROM enrich.areas a USING feature_candidates c
    WHERE a.layer = %(layer)s AND (a.osm_type, a.osm_id) = (c.osm_type, c.osm_id)
      AND NOT EXISTS (
          SELECT 1 FROM built_areas b
          WHERE (b.osm_type, b.osm_id) = (a.osm_type, a.osm_id) AND b.geom IS NOT NULL
      )
"""

UPSERT_AREAS = """
    INSERT INTO enrich.areas AS existing (layer, osm_type, osm_id, tags, geom)
    SELECT %(layer)s, osm_type, osm_id, tags, geom FROM built_areas WHERE geom IS NOT NULL
    ON CONFLICT (layer, osm_type, osm_id) DO UPDATE SET tags = EXCLUDED.tags, geom = EXCLUDED.geom
    WHERE (existing.tags, existing.geom) IS DISTINCT FROM (EXCLUDED.tags, EXCLUDED.geom)
"""

COUNT_SKIPPED_AREAS = "SELECT count(*) FROM built_areas WHERE geom IS NULL"

DROP_BUILT_AREAS = "DROP TABLE built_areas"


@dataclass(frozen=True, slots=True)
class LayerResult:
    built: int
    deleted: int
    skipped: int  # a missing member way or node, not closed, or empty


@dataclass(frozen=True, slots=True)
class FeatureLayer(ABC):
    code: str
    # tag patterns; a raw element belongs to the layer when its tags contain any of them
    match: tuple[dict[str, str], ...]

    @abstractmethod
    async def rebuild(self, conn: AsyncConnection[TupleRow]) -> LayerResult:
        """
        Rebuild this layer's features among feature_candidates, write feature_ways for every
        candidate that matches, and add the old and the new geometry of every feature whose
        geometry changed to changed_features.
        """


@dataclass(frozen=True, slots=True)
class AreaLayer(FeatureLayer):
    """Closed ways and type=multipolygon relations, into enrich.areas."""

    async def rebuild(self, conn: AsyncConnection[TupleRow]) -> LayerResult:
        params = {"layer": self.code, "match": [Jsonb(pattern) for pattern in self.match]}
        await conn.execute(BUILD_AREAS, params)
        await conn.execute("ANALYZE built_areas")
        await conn.execute(WRITE_FEATURE_WAYS)
        # Before the delete and the upsert, which overwrite the old geometry.
        await conn.execute(FIND_CHANGED_AREAS, params)
        deleted = (await conn.execute(DELETE_AREAS, params)).rowcount
        built = (await conn.execute(UPSERT_AREAS, params)).rowcount
        cur = await conn.execute(COUNT_SKIPPED_AREAS)
        row = await cur.fetchone()
        assert row is not None
        skipped: int = row[0]
        # Another area layer creates it again in the same transaction.
        await conn.execute(DROP_BUILT_AREAS)
        return LayerResult(built=built, deleted=deleted, skipped=skipped)
