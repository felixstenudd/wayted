"""SQL for saved routes. %(edge_ids)s and %(forward)s are parallel arrays in route order."""

from app.logbook.route_reviews.queries import REVIEW_OF_ROUTE

_STEPS = """
    SELECT s.seq - 1 AS seq, s.edge_id, s.forward
    FROM unnest(%(edge_ids)s::bigint[], %(forward)s::boolean[]) WITH ORDINALITY
        AS s (edge_id, forward, seq)
"""

# One row per step: where it starts and ends in the graph and whether the activity may go that
# way. Start and end are NULL for an edge that is not in the graph.
STEPS = f"""
    WITH steps AS ({_STEPS})
    SELECT st.seq, st.edge_id,
           CASE WHEN st.forward THEN e.source ELSE e.target END,
           CASE WHEN st.forward THEN e.target ELSE e.source END,
           %(activity)s = ANY (CASE WHEN st.forward THEN e.forward ELSE e.backward END)
    FROM steps st
    LEFT JOIN graph.edges e ON e.id = st.edge_id
    ORDER BY st.seq
"""

# Every edge after the first leaves out its first point, where the edge before ends, so an edge
# adds its point count minus one.
CREATE_ROUTE = f"""
    WITH steps AS ({_STEPS}),
    legs AS (
        SELECT st.seq, st.edge_id, st.forward, e.length_m, e.scores,
               CASE WHEN st.forward THEN e.geom ELSE ST_Reverse(e.geom) END AS geom
        FROM steps st
        JOIN graph.edges e ON e.id = st.edge_id
    ),
    points AS (
        SELECT l.seq, p.path[1] AS n, p.geom
        FROM legs l
        CROSS JOIN LATERAL ST_DumpPoints(l.geom) p
        WHERE l.seq = 0 OR p.path[1] > 1
    ),
    total AS (
        SELECT sum(length_m) AS length_m FROM legs
    ),
    scored AS (
        SELECT kv.key, sum(l.length_m * kv.value::float8) AS weighted, sum(l.length_m) AS length_m
        FROM legs l
        CROSS JOIN LATERAL jsonb_each(l.scores) kv
        GROUP BY kv.key
    ),
    route AS (
        INSERT INTO app.routes (
            user_id, name, activity, shape, target_distance_m, preferences,
            geom, distance_m, scores
        )
        SELECT %(user_id)s, %(name)s, %(activity)s, %(shape)s, %(target_distance_m)s,
               %(preferences)s,
               (SELECT ST_MakeLine(array_agg(geom ORDER BY seq, n)) FROM points),
               total.length_m,
               coalesce(
                   (SELECT jsonb_object_agg(s.key, jsonb_build_object(
                        'mean', round((s.weighted / s.length_m)::numeric, 4),
                        'coverage', round((s.length_m / total.length_m)::numeric, 4)))
                    FROM scored s
                    WHERE s.length_m > 0),
                   '{{}}'
               )
        FROM total
        RETURNING id
    ),
    edges AS (
        INSERT INTO app.route_edges (route_id, seq, edge_id, forward, length_m, last_point)
        SELECT route.id, l.seq, l.edge_id, l.forward, l.length_m,
               sum(ST_NPoints(l.geom) - 1) OVER (ORDER BY l.seq)
        FROM legs l, route
    )
    SELECT id FROM route
"""

GET_ROUTE = f"""
    SELECT r.id, r.name, r.activity, r.shape, r.target_distance_m, r.preferences, r.distance_m,
           r.scores, ST_AsGeoJSON(r.geom, 6)::jsonb AS geometry,
           (SELECT coalesce(jsonb_agg(jsonb_build_object(
                        'seq', e.seq, 'length_m', e.length_m, 'last_point', e.last_point)
                    ORDER BY e.seq), '[]')
            FROM app.route_edges e
            WHERE e.route_id = r.id) AS edges,
           {REVIEW_OF_ROUTE} AS review,
           r.created_at, r.updated_at
    FROM app.routes r
    WHERE r.id = %(route_id)s AND r.user_id = %(user_id)s
"""

# About 5 m: plenty for an overview of many routes.
_SUMMARY = """
    id, name, activity, shape, distance_m, created_at,
    ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, 0.00005), 6)::jsonb AS geometry
"""

LIST_ROUTES = f"""
    SELECT {_SUMMARY}
    FROM app.routes
    WHERE user_id = %(user_id)s
    ORDER BY created_at DESC, id DESC
"""

RENAME_ROUTE = f"""
    UPDATE app.routes SET name = %(name)s, updated_at = now()
    WHERE id = %(route_id)s AND user_id = %(user_id)s
    RETURNING {_SUMMARY}
"""

DELETE_ROUTE = """
    DELETE FROM app.routes WHERE id = %(route_id)s AND user_id = %(user_id)s RETURNING id
"""
