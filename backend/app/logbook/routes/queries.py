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
        SELECT st.seq, st.edge_id, st.forward, e.length_m,
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
    -- Blended between the cells around each point, from any of the tiles it is in (their margins
    -- hold the same cells), as HeightChange samples them. Not smoothed: a watch shows heights as
    -- they are. NULL where there is no height, such as at sea or off the loaded tiles.
    heights AS (
        SELECT p.seq, p.n, (
            SELECT round(ST_Value(t.rast, 1, p.geom, true, 'bilinear')::numeric, 1)::real
            FROM raw.elevation_tiles t
            WHERE ST_Intersects(ST_ConvexHull(t.rast), p.geom)
            LIMIT 1
        ) AS height
        FROM points p
    ),
    total AS (
        SELECT sum(length_m) AS length_m FROM legs
    ),
    route AS (
        INSERT INTO app.routes (
            user_id, name, activity, shape, target_distance_m, preferences, waypoints,
            geom, distance_m, elevations, scores
        )
        SELECT %(user_id)s, %(name)s, %(activity)s, %(shape)s, %(target_distance_m)s,
               %(preferences)s, %(waypoints)s,
               (SELECT ST_MakeLine(array_agg(geom ORDER BY seq, n)) FROM points),
               total.length_m,
               -- A profile with holes would draw cliffs, so one missing height drops them all.
               (SELECT CASE WHEN count(height) = count(*)
                            THEN array_agg(height ORDER BY seq, n) END
                FROM heights),
               routing.route_scores(%(edge_ids)s::bigint[])
        FROM total
        RETURNING id
    ),
    edges AS (
        INSERT INTO app.route_edges (route_id, seq, edge_id, forward, length_m, last_point)
        SELECT route.id, l.seq, l.edge_id, l.forward, l.length_m,
               sum(ST_NPoints(l.geom) - 1) OVER (ORDER BY l.seq)
        FROM legs l, route
    ),
    -- Worked out once, from the graph as it is now: a saved route keeps its line, so its turns
    -- stay with it even when the map changes.
    instructions AS (
        INSERT INTO app.route_instructions (
            route_id, seq, point, distance_m, maneuver, exit, angle, name, way_class
        )
        SELECT route.id, i.seq, i.point, i.distance_m, i.maneuver, i.exit, i.angle, i.name,
               i.way_class
        FROM route,
             routing.instructions(%(edge_ids)s::bigint[], %(forward)s::boolean[], %(activity)s) i
    )
    SELECT id FROM route
"""

GET_ROUTE = f"""
    SELECT r.id, r.name, r.activity, r.shape, r.target_distance_m, r.preferences, r.waypoints,
           r.distance_m, r.scores, ST_AsGeoJSON(r.geom, 6)::jsonb AS geometry,
           (SELECT coalesce(jsonb_agg(jsonb_build_object(
                        'seq', e.seq, 'length_m', e.length_m, 'last_point', e.last_point)
                    ORDER BY e.seq), '[]')
            FROM app.route_edges e
            WHERE e.route_id = r.id) AS edges,
           (SELECT coalesce(jsonb_agg(jsonb_build_object(
                        'seq', i.seq, 'distance_m', i.distance_m, 'maneuver', i.maneuver,
                        'exit', i.exit, 'name', i.name, 'way_class', i.way_class)
                    ORDER BY i.seq), '[]')
            FROM app.route_instructions i
            WHERE i.route_id = r.id) AS instructions,
           {REVIEW_OF_ROUTE} AS review,
           r.created_at, r.updated_at
    FROM app.routes r
    WHERE r.id = %(route_id)s AND r.user_id = %(user_id)s
"""

# The road an instruction turns onto, as its name or ref, else its highway tag ("path").
_ROAD_LABEL = "coalesce(i.name, replace(i.way_class, '_', ' '))"

# An instruction as a short English sentence, "Left onto Storgatan", for apps that show a
# waypoint's name. A road without a name or ref is called by its highway tag, "Left onto path".
_INSTRUCTION_TEXT = f"""
    CASE i.maneuver
        WHEN 'u_turn' THEN 'Turn around'
        WHEN 'roundabout' THEN 'Roundabout, exit ' || i.exit
        ELSE CASE i.maneuver
            WHEN 'slight_left' THEN 'Slight left'
            WHEN 'left' THEN 'Left'
            WHEN 'sharp_left' THEN 'Sharp left'
            WHEN 'slight_right' THEN 'Slight right'
            WHEN 'right' THEN 'Right'
            WHEN 'sharp_right' THEN 'Sharp right'
        END
    END || CASE WHEN i.maneuver = 'u_turn' THEN ''
                ELSE coalesce(' onto ' || {_ROAD_LABEL}, '')
           END
"""

# GPX 1.1 as Strava, Garmin Connect and Komoot read it: a waypoint per instruction, then the route
# as one track segment, heights when the route has them. The schema wants waypoints first and
# their children in its order (ele, name, type). No times: a planned route has not been run yet.
# Coordinates keep 7 decimals, about a centimetre. The XML declaration is added as text because
# xmlroot cannot name the encoding.
EXPORT_GPX = f"""
    SELECT r.name,
           '<?xml version="1.0" encoding="UTF-8"?>' || xmlelement(
               name gpx,
               xmlattributes(
                   'http://www.topografix.com/GPX/1/1' AS xmlns,
                   'http://www.w3.org/2001/XMLSchema-instance' AS "xmlns:xsi",
                   'http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd'
                       AS "xsi:schemaLocation",
                   '1.1' AS version,
                   'wayted' AS creator
               ),
               xmlelement(name metadata, xmlelement(name name, r.name)),
               (SELECT xmlagg(
                           xmlelement(
                               name wpt,
                               xmlattributes(
                                   round(ST_Y(ST_PointN(r.geom, i.point + 1))::numeric, 7) AS lat,
                                   round(ST_X(ST_PointN(r.geom, i.point + 1))::numeric, 7) AS lon
                               ),
                               CASE WHEN r.elevations IS NOT NULL
                                    THEN xmlelement(name ele, r.elevations[i.point + 1])
                               END,
                               xmlelement(name name, {_INSTRUCTION_TEXT}),
                               xmlelement(name type, i.maneuver)
                           ) ORDER BY i.seq)
                FROM app.route_instructions i
                WHERE i.route_id = r.id),
               xmlelement(
                   name trk,
                   xmlelement(name name, r.name),
                   xmlelement(
                       name trkseg,
                       (SELECT xmlagg(
                                   xmlelement(
                                       name trkpt,
                                       xmlattributes(
                                           round(ST_Y(d.geom)::numeric, 7) AS lat,
                                           round(ST_X(d.geom)::numeric, 7) AS lon
                                       ),
                                       -- A NULL child is left out; an empty <ele/> is not.
                                       CASE WHEN r.elevations IS NOT NULL
                                            THEN xmlelement(name ele, r.elevations[d.path[1]])
                                       END
                                   ) ORDER BY d.path[1])
                        FROM ST_DumpPoints(r.geom) d)
                   )
               )
           )::text AS gpx
    FROM app.routes r
    WHERE r.id = %(route_id)s AND r.user_id = %(user_id)s
"""

# A watch's label for a turn, which it shows beside the turn's arrow: the road, or the exit and
# the road for a roundabout ("Exit 2 Storgatan"). The FIT encoder cuts it to the watch's length.
_COURSE_POINT_LABEL = f"""
    CASE WHEN i.maneuver = 'roundabout'
         THEN 'Exit ' || i.exit || coalesce(' ' || {_ROAD_LABEL}, '')
         ELSE {_ROAD_LABEL}
    END
"""

# What a FIT course is made of, as parallel arrays: every point of the line in order with how far
# along the route it is, and every instruction with the index of its point. Distances are
# geodesic from point to point, so a watch's distance to a turn matches the line it draws; they
# end within centimetres of distance_m, which sums the edges' lengths.
EXPORT_FIT = f"""
    WITH route AS (
        SELECT id, name, activity, geom, elevations
        FROM app.routes
        WHERE id = %(route_id)s AND user_id = %(user_id)s
    ),
    steps AS (
        SELECT d.path[1] AS n, d.geom,
               ST_Distance((lag(d.geom) OVER (ORDER BY d.path[1]))::geography, d.geom::geography)
                   AS step_m
        FROM route, ST_DumpPoints(route.geom) d
    ),
    points AS (
        SELECT n, geom, sum(coalesce(step_m, 0)) OVER (ORDER BY n) AS distance_m
        FROM steps
    )
    SELECT r.name, r.activity,
           p.lons, p.lats, p.distances, r.elevations,
           coalesce(t.points, '{{}}'), coalesce(t.maneuvers, '{{}}'),
           coalesce(t.angles, '{{}}'), coalesce(t.labels, '{{}}')
    FROM route r,
         LATERAL (
             SELECT array_agg(ST_X(geom) ORDER BY n) AS lons,
                    array_agg(ST_Y(geom) ORDER BY n) AS lats,
                    array_agg(distance_m ORDER BY n) AS distances
             FROM points
         ) p,
         LATERAL (
             SELECT array_agg(i.point ORDER BY i.seq) AS points,
                    array_agg(i.maneuver ORDER BY i.seq) AS maneuvers,
                    array_agg(i.angle ORDER BY i.seq) AS angles,
                    array_agg({_COURSE_POINT_LABEL} ORDER BY i.seq) AS labels
             FROM app.route_instructions i
             WHERE i.route_id = r.id
         ) t
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
