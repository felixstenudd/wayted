"""Score claimed edges, one key of graph.edges.scores per attribute."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg.types.json import Jsonb

from . import queries
from .layers import FeatureLayer

# Share of a corridor of radius_m around the edge covered by the layers' areas, measured in the
# edge's UTM zone. Areas are clipped to the corridor's box first, so a large park is not
# transformed whole for each of its edges, and unioned, so overlaps count once.
AREA_SHARE = """
    WITH corridors AS (
        SELECT e.id,
               enrich.utm_srid(e.geom) AS srid,
               enrich.expand_m(e.geom, %(radius_m)s) AS box,
               ST_Buffer(ST_Transform(e.geom, enrich.utm_srid(e.geom)), %(radius_m)s) AS corridor
        FROM claimed_edges c JOIN graph.edges e USING (id)
    )
    SELECT c.id AS edge_id,
           least(
               coalesce(ST_Area(ST_Intersection(
                   c.corridor,
                   ST_Union(ST_Transform(ST_ClipByBox2D(a.geom, c.box), c.srid))
               )), 0) / ST_Area(c.corridor),
               1
           ) AS value
    FROM corridors c
    LEFT JOIN enrich.areas a ON a.layer = ANY(%(layers)s) AND a.geom && c.box
    GROUP BY c.id, c.corridor
"""

# Mean over points every sample_m along the edge of 1 - (d / radius_m)^2, d being the distance to
# the nearest feature of the layers, areas or lines, in the edge's UTM zone. Concave: close to
# the water scores nearly the same, the last metres fall fast. Features are clipped to the box
# around the edge first, which keeps every distance under radius_m unchanged.
PROXIMITY = """
    WITH edges AS (
        SELECT e.id,
               enrich.utm_srid(e.geom) AS srid,
               enrich.expand_m(e.geom, %(radius_m)s) AS box,
               ST_Transform(e.geom, enrich.utm_srid(e.geom)) AS line
        FROM claimed_edges c JOIN graph.edges e USING (id)
    ),
    samples AS (
        SELECT e.id, ST_LineInterpolatePoint(e.line, (i - 0.5) / k.n) AS point
        FROM edges e,
             LATERAL (SELECT greatest(1, ceil(ST_Length(e.line) / %(sample_m)s))::int AS n) k,
             LATERAL generate_series(1, k.n) AS i
    ),
    nearby AS (
        SELECT e.id, ST_Collect(ST_Transform(ST_ClipByBox2D(f.geom, e.box), e.srid)) AS geom
        FROM edges e
        JOIN (
            SELECT layer, geom FROM enrich.areas
            UNION ALL
            SELECT layer, geom FROM enrich.lines
        ) f ON f.layer = ANY(%(layers)s) AND f.geom && e.box
        GROUP BY e.id
    )
    SELECT s.id AS edge_id,
           avg(CASE WHEN d.m < %(radius_m)s THEN 1 - (d.m / %(radius_m)s) ^ 2 ELSE 0 END) AS value
    FROM samples s
    LEFT JOIN nearby n USING (id),
    LATERAL (SELECT coalesce(ST_Distance(s.point, n.geom), 'infinity') AS m) d
    GROUP BY s.id
"""

# From the edge's own way: its surface when known, else a guess from the highway, for tracks
# from the tracktype. NULL when neither is known.
SURFACE = """
    SELECT c.id AS edge_id,
           coalesce(
               (%(surfaces)s::jsonb ->> (w.tags ->> 'surface'))::float,
               CASE WHEN w.tags ->> 'highway' = 'track'
                    THEN coalesce(
                        (%(tracktypes)s::jsonb ->> (w.tags ->> 'tracktype'))::float,
                        %(track_default)s
                    )
                    ELSE (%(highways)s::jsonb ->> (w.tags ->> 'highway'))::float
               END
           ) AS value
    FROM claimed_edges c
    JOIN graph.edges e USING (id)
    JOIN graph.ways w ON w.id = e.way_id
"""


@dataclass(frozen=True, slots=True)
class Attribute(ABC):
    key: str  # the key in graph.edges.scores
    layers: tuple[FeatureLayer, ...]

    @abstractmethod
    def score_query(self) -> tuple[str, dict[str, Any]]:
        """SQL returning (edge_id, value) for every row of claimed_edges, and its parameters."""

    @property
    @abstractmethod
    def reach_m(self) -> float:
        """How far from an edge a feature can change its score."""

    async def score(self, conn: AsyncConnection[TupleRow]) -> int:
        """Merge {key: value} into the scores of the claimed edges. Returns the edges written."""
        query, params = self.score_query()
        sql = queries.MERGE_SCORES_HEAD + query + queries.MERGE_SCORES_TAIL
        return (await conn.execute(sql, {**params, "key": self.key})).rowcount


@dataclass(frozen=True, slots=True)
class AreaShare(Attribute):
    radius_m: float

    def score_query(self) -> tuple[str, dict[str, Any]]:
        return AREA_SHARE, {
            "radius_m": self.radius_m,
            "layers": [layer.code for layer in self.layers],
        }

    @property
    def reach_m(self) -> float:
        return self.radius_m


@dataclass(frozen=True, slots=True)
class Proximity(Attribute):
    radius_m: float
    sample_m: float

    def score_query(self) -> tuple[str, dict[str, Any]]:
        return PROXIMITY, {
            "radius_m": self.radius_m,
            "sample_m": self.sample_m,
            "layers": [layer.code for layer in self.layers],
        }

    @property
    def reach_m(self) -> float:
        return self.radius_m


@dataclass(frozen=True, slots=True)
class SurfaceScore(Attribute):
    surfaces: Mapping[str, float]
    highways: Mapping[str, float]
    tracktypes: Mapping[str, float]
    track_default: float

    def score_query(self) -> tuple[str, dict[str, Any]]:
        return SURFACE, {
            "surfaces": Jsonb(dict(self.surfaces)),
            "highways": Jsonb(dict(self.highways)),
            "tracktypes": Jsonb(dict(self.tracktypes)),
            "track_default": self.track_default,
        }

    @property
    def reach_m(self) -> float:
        return 0
