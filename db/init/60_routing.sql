-- Route planning over graph, run by wayted_api. pgRouting reads its network from an SQL string,
-- so the functions here build that string per request instead of copying edges anywhere; nothing
-- in this schema writes to the database.

-- The network as each activity sees it: one row per edge and activity that may use it. Runs as
-- the caller, so it grants nothing that graph and ref do not.
CREATE VIEW routing.activity_edges WITH (security_invoker = true) AS
SELECT
    a.code                    AS activity,
    e.id,
    e.source,
    e.target,
    e.geom,
    e.length_m,
    a.code = ANY (e.forward)  AS forward,
    a.code = ANY (e.backward) AS backward,
    e.scores,
    coalesce(f.factor, 1)     AS factor
FROM graph.edges e
JOIN graph.ways w ON w.id = e.way_id
CROSS JOIN ref.activities a
-- The class the mapper matched against ref.activity_highways.
LEFT JOIN ref.activity_highway_factors f
    ON f.activity = a.code AND f.highway = coalesce(w.tags ->> 'highway', 'ferry')
WHERE a.code = ANY (e.forward) OR a.code = ANY (e.backward);

-- What a request asks of each edge, checked once by routing.make_profile.
CREATE TYPE routing.profile AS (
    -- a ref.activities code
    activity      text,
    -- attribute key -> weight, scaled so the absolute weights sum to 1 (or '{}')
    weights       jsonb,
    -- how far preferences bend cost: an edge costs length * factor * (1 - alpha * preference)
    alpha         double precision,
    -- cost multiplier on edges the route already uses
    reuse_penalty double precision,
    -- cost in metres of a right-angle turn at a junction (see routing.turns_sql)
    turn_m        double precision
);

-- Weights run from -1 (avoid) to 1 (prefer) per edge score key, e.g. {"green": 1}. They are
-- scaled so an edge's preference stays in [-1, 1] however many keys are weighted, which keeps
-- cost between (1 - alpha) and (1 + alpha) times length * factor, and so always positive.
-- Raises invalid_parameter_value for an unknown activity or a value out of range.
CREATE FUNCTION routing.make_profile(
    p_activity      text,
    p_weights       jsonb            DEFAULT '{}',
    p_alpha         double precision DEFAULT 0.7,
    p_reuse_penalty double precision DEFAULT 4,
    p_turn_m        double precision DEFAULT 60
) RETURNS routing.profile
LANGUAGE plpgsql STABLE AS $$
DECLARE
    v_total double precision;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM ref.activities WHERE code = p_activity) THEN
        RAISE EXCEPTION 'unknown activity: %', p_activity USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF jsonb_typeof(p_weights) IS DISTINCT FROM 'object' THEN
        RAISE EXCEPTION 'weights must be an object' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF EXISTS (
        SELECT 1 FROM jsonb_each(p_weights) w
        WHERE jsonb_typeof(w.value) <> 'number' OR abs(w.value::double precision) > 1
    ) THEN
        RAISE EXCEPTION 'weights must be numbers from -1 to 1'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF p_alpha IS NULL OR p_alpha < 0 OR p_alpha >= 1 THEN
        RAISE EXCEPTION 'alpha must be in [0, 1)' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF p_reuse_penalty IS NULL OR p_reuse_penalty < 1 THEN
        RAISE EXCEPTION 'reuse_penalty must be at least 1'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF p_turn_m IS NULL OR p_turn_m < 0 THEN
        RAISE EXCEPTION 'turn_m must be at least 0' USING ERRCODE = 'invalid_parameter_value';
    END IF;

    SELECT sum(abs(w.value::double precision)) INTO v_total FROM jsonb_each(p_weights) w;
    RETURN ROW(
        p_activity,
        coalesce(
            (SELECT jsonb_object_agg(w.key, w.value::double precision / v_total)
             FROM jsonb_each(p_weights) w
             WHERE w.value::double precision <> 0),
            '{}'
        ),
        p_alpha,
        p_reuse_penalty,
        p_turn_m
    )::routing.profile;
END
$$;

-- The edges SQL every pgRouting function takes, for p_activity inside p_area (NULL: everywhere).
-- p_cost is an expression over routing.activity_edges plus "used" (the edge is in p_used); it is
-- -1, pgRouting's "not traversable", where the activity may not go. Edges are read through the
-- GIST index on graph.edges, which is what keeps a call fast on a large graph. p_used is joined,
-- not tested with = ANY, so it is hashed once instead of scanned for every edge.
CREATE FUNCTION routing.edges_sql(
    p_activity text, p_cost text, p_area geometry, p_used bigint[]
) RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT format(
        $sql$
        SELECT id, source, target,
               CASE WHEN forward THEN %1$s ELSE -1 END AS cost,
               CASE WHEN backward THEN %1$s ELSE -1 END AS reverse_cost
        FROM (
            SELECT e.*, u.id IS NOT NULL AS used
            FROM routing.activity_edges e
            LEFT JOIN (SELECT DISTINCT unnest(%2$L::bigint[]) AS id) u ON u.id = e.id
            WHERE e.activity = %3$L %4$s
        ) e
        $sql$,
        p_cost,
        coalesce(p_used, '{}'),
        p_activity,
        CASE WHEN p_area IS NOT NULL
            THEN format('AND ST_Intersects(e.geom, %L::geometry)', p_area)
            ELSE ''
        END
    )
$$;

-- Edges SQL whose cost is plain length, for measuring network distances in metres.
CREATE FUNCTION routing.length_sql(p_activity text, p_area geometry) RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT routing.edges_sql(p_activity, 'length_m', p_area, '{}')
$$;

-- Edges SQL whose cost is what a route optimises: length weighted by highway class and the
-- profile's preferences, and multiplied by the reuse penalty on edges in p_used. A missing score
-- counts as 0, so edges that are not scored yet are neither preferred nor avoided.
CREATE FUNCTION routing.cost_sql(
    p_profile routing.profile, p_area geometry, p_used bigint[] DEFAULT '{}'
) RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT routing.edges_sql(
        p_profile.activity,
        format(
            'length_m * factor * (1 - %s * (%s)) * CASE WHEN used THEN %s ELSE 1 END',
            p_profile.alpha,
            coalesce(
                (SELECT string_agg(
                     format('%s * coalesce((scores ->> %L)::double precision, 0)', w.value, w.key),
                     ' + ' ORDER BY w.key)
                 FROM jsonb_each(p_profile.weights) w),
                '0'
            ),
            p_profile.reuse_penalty
        ),
        p_area,
        p_used
    )
$$;

-- The vertex nearest to p_point that p_activity can use, at most p_max_m metres away; NULL when
-- there is none. The bounding box keeps the index scan from walking the whole table when nothing
-- is near.
CREATE FUNCTION routing.snap(
    p_activity text, p_point geometry, p_max_m double precision
) RETURNS bigint
LANGUAGE sql STABLE AS $$
    SELECT v.id
    FROM graph.vertices v
    WHERE v.geom && ST_Buffer(p_point::geography, p_max_m)::geometry
      AND ST_DWithin(v.geom::geography, p_point::geography, p_max_m)
      AND EXISTS (
          SELECT 1 FROM routing.activity_edges e
          WHERE e.activity = p_activity AND (e.source = v.id OR e.target = v.id)
      )
    ORDER BY v.geom <-> p_point
    LIMIT 1
$$;

-- Edges SQL for travelling p_sql's network backwards, so that a search from a vertex measures the
-- distance to it rather than from it on one-way streets.
CREATE FUNCTION routing.reversed_sql(p_sql text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT format(
        'SELECT id, source, target, reverse_cost AS cost, cost AS reverse_cost FROM (%s) n', p_sql
    )
$$;

-- Every vertex within p_max_m of p_root by p_sql's cost, and how far it is. Output columns are
-- not named like pgRouting's, which would clash with them inside PL/pgSQL.
CREATE FUNCTION routing.distances(p_sql text, p_root bigint, p_max_m double precision)
RETURNS TABLE (vertex bigint, distance_m double precision)
LANGUAGE sql AS $$
    SELECT d.node, d.agg_cost FROM pgr_drivingDistance(p_sql, p_root, p_max_m) d
$$;

-- The smallest angle between two azimuths, in radians.
CREATE FUNCTION routing.angle_between(p_a double precision, p_b double precision)
RETURNS double precision
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT abs(atan2(sin(p_a - p_b), cos(p_a - p_b)))
$$;

-- Routes on routing.turns_sql's network run from a departure to an arrival node: virtual nodes
-- for leaving and reaching a vertex in any direction. Edge travel there is by arc: 2 * id
-- source -> target, 2 * id + 1 back.
CREATE FUNCTION routing.departure(p_vertex bigint) RETURNS bigint
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT -2 * p_vertex
$$;

CREATE FUNCTION routing.arrival(p_vertex bigint) RETURNS bigint
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT -2 * p_vertex - 1
$$;

-- p_sql's network turned into one of arcs, so that a route pays for its turns: moving from one
-- arc to the next costs the next one's cost plus p_turn_m for a right angle at a junction (a
-- vertex where more than two edges meet), scaled linearly from nothing at 30 degrees off
-- straight. Bends between two edges are free, since there is no other way to go. A hairpin looks
-- like turning round however many edges meet there, so from 120 degrees on the cost climbs by up
-- to 1000 m more at 180; turning back onto the edge just travelled counts as 180 degrees anywhere.
-- That is more than the reuse penalty adds to most streets, so a route would rather go back over
-- a street it has used than double back on the spot, and does that only when nothing else is
-- left. The ways out of
-- p_departures and into p_arrivals join their departure and arrival nodes; a route may also
-- start from an arc, to carry on from where the last one arrived. The angles come from the ends
-- of each edge's line.
CREATE FUNCTION routing.turns_sql(
    p_sql text, p_turn_m double precision, p_departures bigint[], p_arrivals bigint[]
) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT format(
        $sql$
        WITH n AS (%1$s),
        arcs AS MATERIALIZED (
            SELECT 2 * n.id AS arc, n.id AS edge, n.source AS tail, n.target AS head, n.cost,
                   ST_Azimuth(ST_PointN(e.geom, 1), ST_PointN(e.geom, 2)) AS leaving,
                   ST_Azimuth(ST_PointN(e.geom, -2), ST_PointN(e.geom, -1)) AS arriving
            FROM n JOIN graph.edges e USING (id)
            WHERE n.cost >= 0
            UNION ALL
            SELECT 2 * n.id + 1, n.id, n.target, n.source, n.reverse_cost,
                   ST_Azimuth(ST_PointN(e.geom, -1), ST_PointN(e.geom, -2)),
                   ST_Azimuth(ST_PointN(e.geom, 2), ST_PointN(e.geom, 1))
            FROM n JOIN graph.edges e USING (id)
            WHERE n.reverse_cost >= 0
        ),
        junctions AS (
            SELECT vertex FROM (
                SELECT tail AS vertex, edge FROM arcs UNION SELECT head, edge FROM arcs
            ) v
            GROUP BY vertex
            HAVING count(*) > 2
        )
        SELECT row_number() OVER () AS id, source, target, cost, -1::float8 AS reverse_cost
        FROM (
            SELECT m.source, m.target,
                   m.cost + CASE WHEN m.turns THEN
                       %2$s * greatest(m.angle - radians(30), 0) / radians(60)
                           + 1000 * greatest(m.angle - radians(120), 0) / radians(60)
                       ELSE 0
                   END AS cost
            FROM (
                SELECT a.arc AS source, b.arc AS target, b.cost,
                       a.edge = b.edge OR j.vertex IS NOT NULL AS turns,
                       CASE WHEN a.edge = b.edge THEN pi()
                            ELSE coalesce(routing.angle_between(a.arriving, b.leaving), 0)
                       END AS angle
                FROM arcs a
                JOIN arcs b ON b.tail = a.head
                LEFT JOIN junctions j ON j.vertex = a.head
            ) m
            UNION ALL
            SELECT routing.departure(tail), arc, cost FROM arcs WHERE tail = ANY (%3$L::bigint[])
            UNION ALL
            SELECT arc, routing.arrival(head), 0 FROM arcs WHERE head = ANY (%4$L::bigint[])
        ) t
        $sql$,
        p_sql,
        p_turn_m,
        coalesce(p_departures, '{}'),
        coalesce(p_arrivals, '{}')
    )
$$;

-- How far arc p_to turns from arc p_from where it follows it, in radians as routing.turns_sql
-- counts it: pi for going back along the same edge.
CREATE FUNCTION routing.turn_angle(p_from bigint, p_to bigint) RETURNS double precision
LANGUAGE sql STABLE AS $$
    SELECT CASE WHEN p_from / 2 = p_to / 2 THEN pi() ELSE coalesce(routing.angle_between(
        (SELECT CASE WHEN p_from % 2 = 0
                     THEN ST_Azimuth(ST_PointN(geom, -2), ST_PointN(geom, -1))
                     ELSE ST_Azimuth(ST_PointN(geom, 2), ST_PointN(geom, 1)) END
         FROM graph.edges WHERE id = p_from / 2),
        (SELECT CASE WHEN p_to % 2 = 0
                     THEN ST_Azimuth(ST_PointN(geom, 1), ST_PointN(geom, 2))
                     ELSE ST_Azimuth(ST_PointN(geom, -1), ST_PointN(geom, -2)) END
         FROM graph.edges WHERE id = p_to / 2)
    ), 0) END
$$;

-- An edge's preference under weights scaled by routing.make_profile, in [-1, 1]. routing.cost_sql
-- writes the same sum out inline, which pgRouting reads faster than a call per edge.
CREATE FUNCTION routing.preference(p_weights jsonb, p_scores jsonb) RETURNS double precision
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT coalesce(
        sum(w.value::double precision * coalesce((p_scores ->> w.key)::double precision, 0)), 0
    )
    FROM jsonb_each(p_weights) w
$$;

-- For each of p_vertices: how many edges p_profile's activity can use there, and how much it
-- likes them (their mean preference). A vertex with one edge is a dead end, which a detour
-- should not aim for: the route would have to come back the way it went. Detours aim for
-- appealing vertices, so the route reaches parks the cost alone would only skirt. Reads
-- graph.edges by its source and target indexes, once for all vertices.
CREATE FUNCTION routing.vertex_stats(p_profile routing.profile, p_vertices bigint[])
RETURNS TABLE (vertex bigint, degree bigint, appeal double precision)
LANGUAGE sql STABLE AS $$
    SELECT u.vertex, count(*), avg(routing.preference(p_profile.weights, u.scores))
    FROM (
        SELECT e.source AS vertex, e.scores FROM graph.edges e
        WHERE e.source = ANY (p_vertices)
          AND p_profile.activity = ANY (e.forward || e.backward)
        UNION ALL
        SELECT e.target, e.scores FROM graph.edges e
        WHERE e.target = ANY (p_vertices)
          AND p_profile.activity = ANY (e.forward || e.backward)
    ) u
    GROUP BY u.vertex
$$;

-- Where a route of p_target_m from p_start to p_finish (NULL: back to the start) can go. No point
-- of an open route is farther than (target - distance) / 2 from the line between its ends, and
-- loop candidates lie within a third of the target of the start, so the area keeps every graph
-- read near the route. The API downloads the tiles covering it before planning.
CREATE FUNCTION routing.search_area(
    p_start geometry, p_finish geometry, p_target_m double precision
) RETURNS geometry
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE
        WHEN p_finish IS NULL THEN
            ST_Buffer(p_start::geography, greatest(0.45 * p_target_m, 500))::geometry
        ELSE
            ST_Buffer(
                ST_MakeLine(p_start, p_finish)::geography,
                greatest(
                    (p_target_m - ST_Distance(p_start::geography, p_finish::geography)) / 2, 500
                )
            )::geometry
    END
$$;

-- A route to try: the vertices it passes in order, from start to finish.
CREATE TYPE routing.candidate AS (
    vias bigint[]
);

-- Loops of about p_goal_m from p_start, as triangles start -> c1 -> c2 -> start. The corners are
-- picked by network distance (a ring at 0.27 to 0.33 of the goal), so the length works out on
-- any street pattern, at 12 bearings with c2 60 degrees after c1, which spreads the loops around
-- the start. Each corner is the most appealing ring vertex within 15 degrees of its bearing (the
-- nearest bearing when there is none), so the preferences choose where the loop goes. Street
-- patterns stretch some directions more than others, so every loop is also tried 15 % smaller
-- and larger; routing.evaluate scores them all in the same call.
CREATE FUNCTION routing.loop_candidates(
    p_profile routing.profile, p_area geometry, p_start bigint, p_goal_m double precision
) RETURNS SETOF routing.candidate
LANGUAGE sql AS $$
    WITH band AS MATERIALIZED (
        SELECT d.vertex, d.distance_m
        FROM routing.distances(
                 routing.length_sql(p_profile.activity, p_area), p_start, 0.33 * 1.15 * p_goal_m
             ) d
        WHERE d.distance_m >= 0.27 * 0.85 * p_goal_m
    ),
    ring AS MATERIALIZED (
        SELECT b.vertex, b.distance_m, ST_Azimuth(s.geom, v.geom) AS azimuth, st.appeal
        FROM band b
        JOIN routing.vertex_stats(p_profile, ARRAY(SELECT vertex FROM band)) st USING (vertex)
        JOIN graph.vertices v ON v.id = b.vertex
        CROSS JOIN (SELECT geom FROM graph.vertices WHERE id = p_start) s
        WHERE st.degree > 1
    ),
    corners AS (
        SELECT
            (SELECT vertex FROM ring
             WHERE distance_m BETWEEN 0.27 * g.goal_m AND 0.33 * g.goal_m
             ORDER BY routing.angle_between(azimuth, b.bearing) > radians(15), appeal DESC,
                      routing.angle_between(azimuth, b.bearing)
             LIMIT 1) AS c1,
            (SELECT vertex FROM ring
             WHERE distance_m BETWEEN 0.27 * g.goal_m AND 0.33 * g.goal_m
             ORDER BY routing.angle_between(azimuth, b.bearing + radians(60)) > radians(15),
                      appeal DESC, routing.angle_between(azimuth, b.bearing + radians(60))
             LIMIT 1) AS c2
        FROM (SELECT radians(d) AS bearing FROM generate_series(0, 330, 30) d) b,
             (SELECT k * p_goal_m AS goal_m FROM unnest(ARRAY[0.85, 1, 1.15]) k) g
    )
    SELECT DISTINCT ROW(ARRAY[p_start, c1, c2, p_start])::routing.candidate
    FROM corners
    WHERE c1 <> c2
$$;

-- Routes of about p_goal_m from p_start to p_finish, picked by network distance from the start
-- (d_start) and to the finish (d_finish):
-- - the direct route;
-- - start -> c -> finish through vertices with d_start + d_finish just under the goal, an
--   ellipse around both ends: the two most appealing from each fifth along it on each side;
-- - start -> c1 -> c2 -> finish, a parallelogram with c1 and c2 at the same bearing from the
--   start and the finish, (goal - direct) / 2 away, for goals far beyond the direct route, where
--   a single detour would come back the way it went. Corners are chosen by appeal, and every
--   shape tried at three sizes, as in routing.loop_candidates.
CREATE FUNCTION routing.detour_candidates(
    p_profile routing.profile,
    p_area geometry,
    p_start bigint,
    p_finish bigint,
    p_goal_m double precision
) RETURNS SETOF routing.candidate
LANGUAGE sql AS $$
    WITH ends AS (
        SELECT s.geom AS start_geom, f.geom AS finish_geom, ST_Azimuth(s.geom, f.geom) AS axis
        FROM graph.vertices s, graph.vertices f
        WHERE s.id = p_start AND f.id = p_finish
    ),
    goals AS (
        SELECT k * p_goal_m AS goal_m FROM unnest(ARRAY[0.85, 1, 1.15]) k
    ),
    from_start AS (
        SELECT * FROM routing.distances(
            routing.length_sql(p_profile.activity, p_area), p_start, 1.15 * p_goal_m
        )
    ),
    to_finish AS (
        SELECT * FROM routing.distances(
            routing.reversed_sql(routing.length_sql(p_profile.activity, p_area)),
            p_finish,
            1.15 * p_goal_m
        )
    ),
    direct AS (
        SELECT distance_m FROM to_finish WHERE vertex = p_start
    ),
    -- Only vertices some shape could use; the stats are read for these alone.
    near AS MATERIALIZED (
        SELECT s.vertex, s.distance_m AS d_start, f.distance_m AS d_finish
        FROM from_start s JOIN to_finish f USING (vertex)
        WHERE s.vertex NOT IN (p_start, p_finish)
          AND (s.distance_m + f.distance_m BETWEEN 0.9 * 0.85 * p_goal_m AND 1.15 * p_goal_m
               OR s.distance_m <= 1.1 * 1.15 * p_goal_m / 2
               OR f.distance_m <= 1.1 * 1.15 * p_goal_m / 2)
    ),
    reach AS MATERIALIZED (
        SELECT
            n.vertex,
            n.d_start,
            n.d_finish,
            ST_Azimuth(ends.start_geom, v.geom) AS from_start,
            ST_Azimuth(ends.finish_geom, v.geom) AS from_finish,
            ends.axis,
            st.appeal
        FROM near n
        JOIN routing.vertex_stats(p_profile, ARRAY(SELECT vertex FROM near)) st USING (vertex)
        JOIN graph.vertices v ON v.id = n.vertex
        CROSS JOIN ends
        WHERE st.degree > 1
    ),
    single AS (
        SELECT reach.vertex, row_number() OVER (
            PARTITION BY goals.goal_m,
                         width_bucket(d_start / (d_start + d_finish), 0, 1, 5),
                         sign(sin(from_start - axis))
            ORDER BY appeal DESC, abs(d_start + d_finish - 0.95 * goals.goal_m)
        ) AS rank
        FROM reach JOIN goals ON d_start + d_finish BETWEEN 0.9 * goal_m AND goal_m
    ),
    side AS (
        SELECT (goals.goal_m - direct.distance_m) / 2 AS r
        FROM direct, goals
        WHERE direct.distance_m < goals.goal_m / 2
    ),
    parallelograms AS (
        SELECT
            (SELECT vertex FROM reach
             WHERE d_start BETWEEN 0.9 * side.r AND 1.1 * side.r
             ORDER BY routing.angle_between(from_start, axis + b.turn) > radians(15), appeal DESC,
                      routing.angle_between(from_start, axis + b.turn)
             LIMIT 1) AS c1,
            (SELECT vertex FROM reach
             WHERE d_finish BETWEEN 0.9 * side.r AND 1.1 * side.r
             ORDER BY routing.angle_between(from_finish, axis + b.turn) > radians(15), appeal DESC,
                      routing.angle_between(from_finish, axis + b.turn)
             LIMIT 1) AS c2
        FROM (SELECT radians(d) AS turn FROM unnest(ARRAY[-120, -90, -60, 60, 90, 120]) d) b,
             side
    )
    SELECT ROW(ARRAY[p_start, p_finish])::routing.candidate
    UNION
    SELECT ROW(ARRAY[p_start, vertex, p_finish])::routing.candidate FROM single WHERE rank <= 2
    UNION
    SELECT ROW(ARRAY[p_start, c1, c2, p_finish])::routing.candidate
    FROM parallelograms
    WHERE c1 <> c2
$$;

-- How well a route of p_length_m fits, lower is better: the share by which it misses the target,
-- 0.3 per unit of length-weighted preference below 1, and half the share travelled twice.
CREATE FUNCTION routing.score(
    p_target_m   double precision,
    p_length_m   double precision,
    p_preference double precision,
    p_overlap_m  double precision
) RETURNS double precision
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT abs(p_length_m - p_target_m) / p_target_m
        + 0.3 * (1 - coalesce(p_preference, 0))
        + 0.5 * coalesce(p_overlap_m / nullif(p_length_m, 0), 0)
$$;

-- A candidate as pgRouting routes it: its length, length-weighted preference, length on edges it
-- uses more than once, and a score where lower is better.
CREATE TYPE routing.evaluation AS (
    vias       bigint[],
    length_m   double precision,
    preference double precision,
    overlap_m  double precision,
    score      double precision
);

-- Every candidate evaluated from one pgr_dijkstra call over the distinct legs of all of them, on
-- routing.turns_sql's network so that turns count as they will on the route. Legs are found apart,
-- so a leg does not know how the one before arrived; where its cheapest way out of the via turns
-- back sharply (more than 120 degrees, where a hairpin starts to cost) from the way the last leg
-- came in, it is found again from that arc, in one more call for all such legs, as
-- routing.route_edges will route it. The score is routing.score, plus 1 when the route still has
-- to turn back at a via (one at the end of a spur, or where every way on is a hairpin), which
-- only a route with no other candidate takes. Legs are evaluated without the reuse penalty that the final route gets, so retracing
-- counts for less than it appears. Candidates with a leg that cannot be travelled are left out.
CREATE FUNCTION routing.evaluate(
    p_profile routing.profile,
    p_area geometry,
    p_target_m double precision,
    p_candidates routing.candidate[]
) RETURNS SETOF routing.evaluation
LANGUAGE sql AS $$
    WITH candidates AS (
        SELECT c.vias, c.n FROM unnest(p_candidates) WITH ORDINALITY AS c(vias, n)
    ),
    legs AS (
        SELECT c.n, l.i, c.vias[l.i] AS source, c.vias[l.i + 1] AS target
        FROM candidates c, generate_series(1, cardinality(c.vias) - 1) AS l(i)
        WHERE c.vias[l.i] <> c.vias[l.i + 1]
    ),
    -- Each leg and the leg after it; vias repeated in a row are skipped.
    follows AS (
        SELECT a.n, a.i AS before, min(b.i) AS after
        FROM legs a JOIN legs b ON b.n = a.n AND b.i > a.i
        GROUP BY a.n, a.i
    ),
    pairs AS (
        SELECT coalesce(array_agg(source), '{}') AS sources,
               coalesce(array_agg(target), '{}') AS targets
        FROM (SELECT DISTINCT source, target FROM legs) d
    ),
    paths AS (
        SELECT -p.start_vid / 2 AS source, -(p.end_vid + 1) / 2 AS target, p.node AS arc,
               p.path_seq
        FROM pairs, pgr_dijkstra(
            routing.turns_sql(
                routing.cost_sql(p_profile, p_area), p_profile.turn_m, pairs.sources, pairs.targets
            ),
            format(
                $sql$
                SELECT routing.departure(source) AS source, routing.arrival(target) AS target
                FROM unnest(%L::bigint[], %L::bigint[]) AS c(source, target)
                $sql$,
                pairs.sources, pairs.targets
            )
        ) p
        -- Arc nodes; the departure and arrival nodes are negative.
        WHERE p.node >= 0
    ),
    ends AS (
        SELECT source, target,
               (array_agg(arc ORDER BY path_seq))[1] AS first_arc,
               (array_agg(arc ORDER BY path_seq DESC))[1] AS last_arc
        FROM paths
        GROUP BY source, target
    ),
    turning AS (
        SELECT b.n, b.i, ea.last_arc AS from_arc, b.target
        FROM follows f
        JOIN legs a ON a.n = f.n AND a.i = f.before
        JOIN legs b ON b.n = f.n AND b.i = f.after
        JOIN ends ea ON ea.source = a.source AND ea.target = a.target
        JOIN ends eb ON eb.source = b.source AND eb.target = b.target
        WHERE routing.turn_angle(ea.last_arc, eb.first_arc) > radians(120)
    ),
    redone AS (
        SELECT p.start_vid AS from_arc, -(p.end_vid + 1) / 2 AS target, p.node AS arc,
               p.path_seq
        FROM (
            SELECT array_agg(from_arc) AS arcs, array_agg(target) AS targets
            FROM (SELECT DISTINCT from_arc, target FROM turning) d
            -- No row, and so no call, when no leg turns back.
            HAVING count(*) > 0
        ) t, pgr_dijkstra(
            routing.turns_sql(
                routing.cost_sql(p_profile, p_area), p_profile.turn_m, '{}', t.targets
            ),
            format(
                $sql$
                SELECT source, routing.arrival(target) AS target
                FROM unnest(%L::bigint[], %L::bigint[]) AS c(source, target)
                $sql$,
                t.arcs, t.targets
            )
        ) p
        -- The arc it starts from belongs to the leg before.
        WHERE p.node >= 0 AND p.node <> p.start_vid
    ),
    -- Redone legs whose way on still turns back sharply.
    turning_round AS (
        SELECT DISTINCT t.n
        FROM turning t
        JOIN redone r ON r.from_arc = t.from_arc AND r.target = t.target
        WHERE routing.turn_angle(t.from_arc, r.arc) > radians(120)
          AND r.path_seq = (
              SELECT min(x.path_seq) FROM redone x
              WHERE x.from_arc = t.from_arc AND x.target = t.target
          )
    ),
    complete AS (
        SELECT l.n FROM legs l
        GROUP BY l.n
        HAVING bool_and(EXISTS (
            SELECT 1 FROM ends e WHERE e.source = l.source AND e.target = l.target
        ))
    ),
    leg_edges AS (
        SELECT l.n, p.arc / 2 AS edge
        FROM legs l
        JOIN paths p ON p.source = l.source AND p.target = l.target
        WHERE NOT EXISTS (SELECT 1 FROM turning t WHERE t.n = l.n AND t.i = l.i)
        UNION ALL
        SELECT t.n, r.arc / 2
        FROM turning t
        JOIN redone r ON r.from_arc = t.from_arc AND r.target = t.target
    ),
    uses AS (
        SELECT l.n, l.edge, count(*) AS times
        FROM leg_edges l
        JOIN complete USING (n)
        GROUP BY l.n, l.edge
    ),
    totals AS (
        SELECT
            u.n,
            sum(e.length_m * u.times) AS length_m,
            sum(e.length_m * u.times * routing.preference(p_profile.weights, e.scores))
                AS preferred_m,
            sum(e.length_m * (u.times - 1)) AS overlap_m
        FROM uses u JOIN graph.edges e ON e.id = u.edge
        GROUP BY u.n
    )
    SELECT ROW(
        c.vias,
        t.length_m,
        t.preferred_m / nullif(t.length_m, 0),
        t.overlap_m,
        routing.score(p_target_m, t.length_m, t.preferred_m / nullif(t.length_m, 0), t.overlap_m)
            + CASE WHEN r.n IS NULL THEN 0 ELSE 1 END
    )::routing.evaluation
    FROM totals t
    JOIN candidates c USING (n)
    LEFT JOIN turning_round r USING (n)
$$;

-- The edges of the route through p_vias in travel order, with the vertex each is entered from.
-- Legs are routed one after another on routing.turns_sql's network, each with the edges before it
-- in p_used, so the reuse penalty keeps a leg off the streets the route has already taken where
-- it can. Each leg after the first starts from the arc the last one arrived by, so the turn at a
-- via costs what any other turn does and the route does not double back there.
-- Raises no_data_found (detail unreachable) when a leg cannot be travelled.
CREATE FUNCTION routing.route_edges(
    p_profile routing.profile, p_area geometry, p_vias bigint[]
) RETURNS TABLE (step integer, vertex bigint, edge_id bigint)
LANGUAGE plpgsql AS $$
DECLARE
    v_used bigint[] := '{}';
    -- The departure node of the first leg, then the arc each leg arrived by.
    v_from bigint := routing.departure(p_vias[1]);
    v_arcs bigint[];
    v_step integer := 0;
BEGIN
    FOR i IN 1 .. cardinality(p_vias) - 1 LOOP
        CONTINUE WHEN p_vias[i] = p_vias[i + 1];
        SELECT array_agg(d.node ORDER BY d.seq) INTO v_arcs
        FROM pgr_dijkstra(
            routing.turns_sql(
                routing.cost_sql(p_profile, p_area, v_used),
                p_profile.turn_m,
                CASE WHEN i = 1 THEN ARRAY[p_vias[1]] END,
                ARRAY[p_vias[i + 1]]
            ),
            v_from,
            routing.arrival(p_vias[i + 1])
        ) d
        -- The arc the leg starts from was travelled by the leg before.
        WHERE d.node >= 0 AND d.node <> v_from;
        IF v_arcs IS NULL THEN
            RAISE EXCEPTION 'no path from vertex % to %', p_vias[i], p_vias[i + 1]
                USING ERRCODE = 'no_data_found', DETAIL = 'unreachable';
        END IF;
        RETURN QUERY
            SELECT v_step + u.n::integer,
                   CASE WHEN u.arc % 2 = 0 THEN e.source ELSE e.target END,
                   e.id
            FROM unnest(v_arcs) WITH ORDINALITY AS u(arc, n)
            JOIN graph.edges e ON e.id = u.arc / 2;
        v_step := v_step + cardinality(v_arcs);
        v_used := v_used || ARRAY(SELECT a / 2 FROM unnest(v_arcs) a);
        v_from := v_arcs[cardinality(v_arcs)];
    END LOOP;
END
$$;

-- The route through p_vias as the API returns it: the line in travel order, its length, the
-- length-weighted share of every edge score along it, the length travelled more than once, the
-- edge ids in order and p_warnings.
CREATE FUNCTION routing.route_json(
    p_profile routing.profile, p_area geometry, p_vias bigint[], p_warnings text[]
) RETURNS jsonb
LANGUAGE sql AS $$
    WITH path AS MATERIALIZED (
        SELECT
            r.step,
            e.id,
            e.length_m,
            e.scores,
            -- pgRouting gives the vertex an edge is entered from; turn the rest around.
            CASE WHEN r.vertex = e.source THEN e.geom ELSE ST_Reverse(e.geom) END AS geom
        FROM routing.route_edges(p_profile, p_area, p_vias) r
        JOIN graph.edges e ON e.id = r.edge_id
    ),
    -- Summed in travel order, so the same route always has the same length to the last digit.
    total AS (
        SELECT sum(length_m ORDER BY step) AS length_m FROM path
    ),
    shares AS (
        SELECT coalesce(jsonb_object_agg(k.key, k.scored_m / nullif(total.length_m, 0)), '{}')
            AS scores
        FROM total, (
            SELECT key, sum(p.length_m * (p.scores ->> key)::double precision) AS scored_m
            FROM path p, jsonb_object_keys(p.scores) AS key
            GROUP BY key
        ) k
    ),
    reused AS (
        SELECT coalesce(sum(length_m * (times - 1)), 0) AS length_m
        FROM (SELECT min(length_m) AS length_m, count(*) AS times FROM path GROUP BY id) u
    )
    SELECT jsonb_build_object(
        'geometry', (SELECT ST_AsGeoJSON(ST_MakeLine(geom ORDER BY step))::jsonb FROM path),
        'length_m', total.length_m,
        'scores', shares.scores,
        'reused_m', reused.length_m,
        'edges', (SELECT to_jsonb(array_agg(id ORDER BY step)) FROM path),
        'warnings', to_jsonb(p_warnings)
    )
    FROM total, shares, reused
$$;

-- Plans a route of about p_target_m for p_activity from p_start to p_finish, or back to p_start
-- when p_finish is NULL, weighting edge scores by p_weights (see routing.make_profile). Options:
-- alpha, reuse_penalty and turn_m (see routing.profile), tolerance (0.07: how far the length may miss the
-- target) and snap_m (200: how far a point may be from the road it starts on).
-- Candidates are generated and scored in bulk; if the best misses the tolerance, the goal is
-- scaled by how much it missed and candidates are tried once more. Evaluation leaves out the
-- reuse penalty, so a route can come out otherwise than evaluated; when it misses the tolerance,
-- the next best candidates are routed too, up to three in all, and the one whose route scores
-- best is returned. Warnings, judged on that route: too_short (the finish is farther than the
-- target), target_missed (it misses the target by more than the tolerance).
-- Raises invalid_parameter_value for bad input, and no_data_found when there is no route; its
-- detail says why, for the API to pass on: start_off_road or finish_off_road (no road within
-- snap_m), unreachable (no way from the start to the finish) or no_loop (too few roads around
-- the start to come back by another way).
CREATE FUNCTION routing.plan_route(
    p_activity text,
    p_start    geometry,
    p_finish   geometry,
    p_target_m double precision,
    p_weights  jsonb DEFAULT '{}',
    p_options  jsonb DEFAULT '{}'
) RETURNS jsonb
LANGUAGE plpgsql AS $$
DECLARE
    v_tolerance double precision;
    v_snap_m    double precision;
    v_profile   routing.profile;
    v_area      geometry;
    v_start     bigint;
    v_finish    bigint;
    v_goal_m    double precision;
    -- All NULL until a candidate is found.
    v_best      routing.evaluation;
    v_retry     routing.evaluation;
    -- The best few of every attempt, to route when the best one comes out wrong.
    v_ranked    routing.evaluation[] := '{}';
    v_try       routing.evaluation;
    v_routed    jsonb;
    v_score     double precision;
    v_route     jsonb;
    v_vias      bigint[];
    v_best_score double precision;
    v_length_m  double precision;
BEGIN
    IF jsonb_typeof(p_options) IS DISTINCT FROM 'object'
        OR p_options - ARRAY['alpha', 'reuse_penalty', 'turn_m', 'tolerance', 'snap_m'] <> '{}'
        OR EXISTS (SELECT 1 FROM jsonb_each(p_options) o WHERE jsonb_typeof(o.value) <> 'number')
    THEN
        RAISE EXCEPTION
            'options may only be numbers named alpha, reuse_penalty, turn_m, tolerance, snap_m'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;
    v_tolerance := coalesce((p_options ->> 'tolerance')::double precision, 0.07);
    v_snap_m := coalesce((p_options ->> 'snap_m')::double precision, 200);
    IF p_target_m IS NULL OR p_target_m <= 0 OR v_tolerance <= 0 OR v_tolerance >= 1
        OR v_snap_m <= 0 OR p_start IS NULL
    THEN
        RAISE EXCEPTION 'need a start, a positive target and snap_m, and a tolerance in (0, 1)'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;
    v_profile := routing.make_profile(
        p_activity,
        p_weights,
        coalesce((p_options ->> 'alpha')::double precision, 0.7),
        coalesce((p_options ->> 'reuse_penalty')::double precision, 4),
        coalesce((p_options ->> 'turn_m')::double precision, 60)
    );

    v_area := routing.search_area(p_start, p_finish, p_target_m);
    v_start := routing.snap(p_activity, p_start, v_snap_m);
    IF v_start IS NULL THEN
        RAISE EXCEPTION 'no road near the start'
            USING ERRCODE = 'no_data_found', DETAIL = 'start_off_road';
    END IF;
    v_finish := CASE
        WHEN p_finish IS NULL THEN v_start
        ELSE routing.snap(p_activity, p_finish, v_snap_m)
    END;
    IF v_finish IS NULL THEN
        RAISE EXCEPTION 'no road near the finish'
            USING ERRCODE = 'no_data_found', DETAIL = 'finish_off_road';
    END IF;

    v_goal_m := p_target_m;
    FOR attempt IN 1 .. 2 LOOP
        v_ranked := v_ranked || ARRAY(
            SELECT e
            FROM routing.evaluate(
                v_profile,
                v_area,
                p_target_m,
                ARRAY(
                    SELECT c FROM routing.loop_candidates(v_profile, v_area, v_start, v_goal_m) c
                    WHERE v_start = v_finish
                    UNION ALL
                    SELECT c
                    FROM routing.detour_candidates(v_profile, v_area, v_start, v_finish, v_goal_m) c
                    WHERE v_start <> v_finish
                )
            ) e
            ORDER BY e.score
            LIMIT 3
        );
        SELECT * INTO v_retry FROM unnest(v_ranked) e ORDER BY e.score LIMIT 1;
        IF FOUND AND (v_best.vias IS NULL OR v_retry.score < v_best.score) THEN
            v_best := v_retry;
        END IF;
        EXIT WHEN v_best.vias IS NULL
            OR abs(v_best.length_m - p_target_m) <= v_tolerance * p_target_m
            -- Only the direct route is left; a longer goal finds nothing shorter.
            OR (cardinality(v_best.vias) = 2 AND v_best.length_m > p_target_m);
        v_goal_m := v_goal_m * p_target_m / v_best.length_m;
    END LOOP;

    IF v_best.vias IS NULL THEN
        IF v_start = v_finish THEN
            RAISE EXCEPTION 'too few roads around the start for a loop'
                USING ERRCODE = 'no_data_found', DETAIL = 'no_loop';
        END IF;
        RAISE EXCEPTION 'the finish cannot be reached from the start'
            USING ERRCODE = 'no_data_found', DETAIL = 'unreachable';
    END IF;
    FOR v_try IN
        SELECT d.* FROM (
            SELECT DISTINCT ON (e.vias) e.* FROM unnest(v_ranked) e ORDER BY e.vias, e.score
        ) d
        ORDER BY d.score
        LIMIT 3
    LOOP
        v_routed := routing.route_json(v_profile, v_area, v_try.vias, '{}');
        v_length_m := (v_routed ->> 'length_m')::double precision;
        v_score := routing.score(
            p_target_m,
            v_length_m,
            routing.preference(v_profile.weights, v_routed -> 'scores'),
            (v_routed ->> 'reused_m')::double precision
        );
        IF v_route IS NULL OR v_score < v_best_score THEN
            v_route := v_routed;
            v_vias := v_try.vias;
            v_best_score := v_score;
        END IF;
        EXIT WHEN abs((v_route ->> 'length_m')::double precision - p_target_m)
            <= v_tolerance * p_target_m;
    END LOOP;

    v_length_m := (v_route ->> 'length_m')::double precision;
    IF abs(v_length_m - p_target_m) > v_tolerance * p_target_m THEN
        v_route := jsonb_set(v_route, '{warnings}', to_jsonb(ARRAY[CASE
            WHEN cardinality(v_vias) = 2 AND v_length_m > p_target_m THEN 'too_short'
            ELSE 'target_missed'
        END]));
    END IF;
    RETURN v_route;
END
$$;
