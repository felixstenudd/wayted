"""Turn raw elements into feature geometry, one table per kind of geometry."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import LiteralString

from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg.types.json import Jsonb

# Matching candidates, with their member ways in order and a polygon, or NULL when a member
# way or node is missing, the ways form no closed ring, or nothing is left after repair.
# ST_BuildArea nests rings by geometry, so outer and inner roles are not read. Self-crossing
# or duplicate lines give it nothing; only then are they noded, which can lose a touching hole.
BUILD_AREAS = """
    CREATE TEMP TABLE built_features ON COMMIT DROP AS
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
                   ST_CollectionExtract(ST_MakeValid(coalesce(
                       ST_BuildArea(ST_Collect(line)),
                       ST_BuildArea(ST_Node(ST_Collect(line)))
                   )), 3)
               END AS geom
        FROM lines
        GROUP BY osm_type, osm_id
    )
    SELECT m.osm_type, m.osm_id, m.tags, m.way_ids,
           CASE WHEN NOT ST_IsEmpty(s.geom) THEN ST_Multi(s.geom) END AS geom
    FROM matched m JOIN shapes s USING (osm_type, osm_id)
"""

# Matching candidate ways and their line, or NULL when a node is missing or there are fewer
# than two.
BUILD_LINES = """
    CREATE TEMP TABLE built_features ON COMMIT DROP AS
    SELECT c.osm_type, c.osm_id, w.tags, ARRAY[w.id] AS way_ids,
           (
               SELECT CASE WHEN count(n.id) = cardinality(w.node_ids) AND count(n.id) >= 2
                           THEN ST_Multi(ST_MakeLine(n.geom ORDER BY p.ord)) END
               FROM unnest(w.node_ids) WITH ORDINALITY AS p(id, ord)
               LEFT JOIN raw.osm_nodes n ON n.id = p.id
           ) AS geom
    FROM feature_candidates c JOIN raw.osm_ways w ON w.id = c.osm_id
    WHERE c.osm_type = 'way' AND w.tags @> ANY(%(match)s::jsonb[])
"""

WRITE_FEATURE_WAYS = """
    INSERT INTO enrich.feature_ways (osm_type, osm_id, way_id)
    SELECT osm_type, osm_id, unnest(way_ids) FROM built_features
    ON CONFLICT DO NOTHING
"""

# The statements below are formatted with the layer's table.

# Old geometry of candidates that lost or changed it, and new geometry that differs.
FIND_CHANGED = """
    INSERT INTO changed_features (layer, geom)
    SELECT a.layer, a.geom
    FROM {table} a
    JOIN feature_candidates c USING (osm_type, osm_id)
    LEFT JOIN built_features b USING (osm_type, osm_id)
    WHERE a.layer = %(layer)s AND a.geom IS DISTINCT FROM b.geom
    UNION ALL
    SELECT %(layer)s, b.geom
    FROM built_features b
    LEFT JOIN {table} a
        ON (a.layer, a.osm_type, a.osm_id) = (%(layer)s, b.osm_type, b.osm_id)
    WHERE b.geom IS NOT NULL AND a.geom IS DISTINCT FROM b.geom
"""

DELETE_FEATURES = """
    DELETE FROM {table} a USING feature_candidates c
    WHERE a.layer = %(layer)s AND (a.osm_type, a.osm_id) = (c.osm_type, c.osm_id)
      AND NOT EXISTS (
          SELECT 1 FROM built_features b
          WHERE (b.osm_type, b.osm_id) = (a.osm_type, a.osm_id) AND b.geom IS NOT NULL
      )
"""

UPSERT_FEATURES = """
    INSERT INTO {table} AS existing (layer, osm_type, osm_id, tags, geom)
    SELECT %(layer)s, osm_type, osm_id, tags, geom FROM built_features WHERE geom IS NOT NULL
    ON CONFLICT (layer, osm_type, osm_id) DO UPDATE SET tags = EXCLUDED.tags, geom = EXCLUDED.geom
    WHERE (existing.tags, existing.geom) IS DISTINCT FROM (EXCLUDED.tags, EXCLUDED.geom)
"""

COUNT_SKIPPED = "SELECT count(*) FROM built_features WHERE geom IS NULL"

DROP_BUILT = "DROP TABLE built_features"


@dataclass(frozen=True, slots=True)
class LayerResult:
    built: int
    deleted: int
    skipped: int  # a missing way or node, an open area, a line under two nodes, or empty


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
        return await _rebuild(conn, self, BUILD_AREAS, "enrich.areas")


@dataclass(frozen=True, slots=True)
class LineLayer(FeatureLayer):
    """Ways, open or closed, into enrich.lines."""

    async def rebuild(self, conn: AsyncConnection[TupleRow]) -> LayerResult:
        return await _rebuild(conn, self, BUILD_LINES, "enrich.lines")


async def _rebuild(
    conn: AsyncConnection[TupleRow], layer: FeatureLayer, build: str, table: LiteralString
) -> LayerResult:
    params = {"layer": layer.code, "match": [Jsonb(pattern) for pattern in layer.match]}
    await conn.execute(build, params)
    await conn.execute("ANALYZE built_features")
    await conn.execute(WRITE_FEATURE_WAYS)
    # Before the delete and the upsert, which overwrite the old geometry.
    await conn.execute(FIND_CHANGED.format(table=table), params)
    deleted = (await conn.execute(DELETE_FEATURES.format(table=table), params)).rowcount
    built = (await conn.execute(UPSERT_FEATURES.format(table=table), params)).rowcount
    cur = await conn.execute(COUNT_SKIPPED)
    row = await cur.fetchone()
    assert row is not None
    skipped: int = row[0]
    # Another layer creates it again in the same transaction.
    await conn.execute(DROP_BUILT)
    return LayerResult(built=built, deleted=deleted, skipped=skipped)
