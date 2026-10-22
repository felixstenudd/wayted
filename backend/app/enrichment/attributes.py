"""Score claimed edges, one key of graph.edges.scores per attribute."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

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


# How much the edge climbs and drops for its length, from heights sampled every sample_m along
# it. A height is the mean of the point and four points smooth_m north, east, south and west of
# it, each blended between the cells of the elevation tile it lies in (any of the tiles a point
# is in: their margins hold the same cells), which evens out trees and roofs. Rises and drops
# are counted through enrich.climb with threshold_m, and each is at least the difference
# between the ends once that is ends_m or more, so a long even hill split into short edges that
# each rise less than threshold_m still counts. Without the smoothing and ends_m, noise on a
# short edge would read as a steep one. The height model sees the deck of a bridge as the valley
# below it, so bridges and tunnels count only their ends; ferries count nothing. Besides the
# score, returns the metres climbed and dropped from source to target. Ups and downs score alike:
# an average change of full_grade (the share of the length) or more scores 1. An edge without
# heights, such as before its tile is downloaded, has neither score nor metres, so it counts as
# unknown rather than flat.
HEIGHT_CHANGE = """
    WITH edges AS (
        SELECT e.id, e.geom, e.length_m,
               coalesce(w.tags ->> 'bridge', 'no') <> 'no'
                   OR coalesce(w.tags ->> 'tunnel', 'no') <> 'no' AS level,
               w.tags ->> 'route' = 'ferry' AND NOT w.tags ? 'highway' AS ferry
        FROM claimed_edges c
        JOIN graph.edges e USING (id)
        JOIN graph.ways w ON w.id = e.way_id
    ),
    samples AS (
        SELECT e.id, (d).path[1] AS n, h.height
        FROM edges e
        CROSS JOIN LATERAL ST_DumpPoints(
            ST_Segmentize(e.geom::geography, %(sample_m)s)::geometry
        ) d
        CROSS JOIN LATERAL (
            SELECT avg((
                SELECT ST_Value(t.rast, 1, o.point, true, 'bilinear')
                FROM raw.elevation_tiles t
                WHERE ST_Intersects(ST_ConvexHull(t.rast), o.point)
                LIMIT 1
            )) AS height
            FROM (
                SELECT (d).geom AS point
                UNION ALL
                SELECT ST_Project((d).geom::geography, %(smooth_m)s, radians(a))::geometry
                FROM unnest(ARRAY[0, 90, 180, 270]) a
            ) o
        ) h
        WHERE NOT e.ferry
    ),
    profiles AS (
        SELECT id, array_agg(height ORDER BY n) AS heights
        FROM samples
        WHERE height IS NOT NULL
        GROUP BY id
    ),
    climbs AS (
        SELECT e.id, e.length_m,
               CASE WHEN e.ferry THEN 0
                    WHEN p.heights IS NULL THEN NULL
                    WHEN e.level THEN greatest(ends.rise_m, 0)
                    ELSE greatest(c.ascent_m, ends.rise_m) END AS ascent_m,
               CASE WHEN e.ferry THEN 0
                    WHEN p.heights IS NULL THEN NULL
                    WHEN e.level THEN greatest(-ends.rise_m, 0)
                    ELSE greatest(c.descent_m, -ends.rise_m) END AS descent_m
        FROM edges e
        LEFT JOIN profiles p USING (id)
        CROSS JOIN LATERAL enrich.climb(p.heights, %(threshold_m)s) c
        CROSS JOIN LATERAL (
            SELECT CASE WHEN abs(r.m) < %(ends_m)s THEN 0 ELSE r.m END AS rise_m
            FROM (SELECT p.heights[cardinality(p.heights)] - p.heights[1] AS m) r
        ) ends
    )
    SELECT id AS edge_id, ascent_m, descent_m,
           CASE WHEN ascent_m IS NULL THEN NULL WHEN length_m = 0 THEN 0 ELSE least(
               (ascent_m + descent_m) / length_m / %(full_grade)s, 1
           ) END AS value
    FROM climbs
"""


@dataclass(frozen=True, slots=True)
class Attribute(ABC):
    key: str  # the key in graph.edges.scores
    layers: tuple[FeatureLayer, ...]
    # graph.edges columns the score query also returns, written along with the score
    columns: ClassVar[tuple[str, ...]] = ()

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
        sql = queries.merge_scores_head(self.columns) + query + queries.MERGE_SCORES_TAIL
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


@dataclass(frozen=True, slots=True)
class HeightChange(Attribute):
    """Edges are queued for it when their elevation tiles change, not by feature layers."""

    columns = ("ascent_m", "descent_m")
    sample_m: float
    smooth_m: float
    threshold_m: float
    ends_m: float
    full_grade: float

    def score_query(self) -> tuple[str, dict[str, Any]]:
        return HEIGHT_CHANGE, {
            "sample_m": self.sample_m,
            "smooth_m": self.smooth_m,
            "threshold_m": self.threshold_m,
            "ends_m": self.ends_m,
            "full_grade": self.full_grade,
        }

    @property
    def reach_m(self) -> float:
        """A height this far from the edge is in the mean of one of its samples."""
        return self.smooth_m
