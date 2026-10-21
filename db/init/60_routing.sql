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

-- Every setting the planner is tuned by, grouped by the stage that reads it, at the value it
-- starts from. Each stage reads only its own group, so one behaviour can be tuned without
-- touching the others, and a request may override any of them (see routing.make_profile). Some
-- start from other values for an activity (see routing.activity_defaults).
-- Fractions of a goal or target are shares of its length; lists are the sizes a stage tries.
-- - cost: alpha, how far preferences bend an edge's cost (see routing.cost_sql).
-- - turns: the cost of a turn (see routing.turns_sql): turn_m at a right angle, nothing up to
--   free_deg off straight, and from hairpin_deg on up to hairpin_m more at 180 degrees.
-- - legs: reuse_penalty, the cost multiplier on edges the route already uses, and the corridor a
--   leg is routed in first (see routing.route_edges).
-- - area: how far around the start and finish the planner reads (see routing.search_area).
-- - loops, detours: where candidates go (see routing.loop_candidates, routing.detour_candidates).
-- - evaluate: when a candidate's turn at a via counts against it (see routing.evaluate).
-- - doubling: the rules routing.doubled_m measures by.
-- - score: what routing.score weighs, besides missing the target.
-- - plan: tolerance, how far the length may miss the target; snap_m, how far a point may be from
--   the road it starts on; loop_network, how much road a loop needs around its start, as a share
--   of the target (see routing.snap_points); attempts at a goal, candidates kept from each and
--   routes tried.
-- - options: how many routes a plan offers at most, the best among them (count); how many
--   candidates are routed to find the others (routed); how much of the shorter of two options
--   they may share (overlap); how much worse than the best an option may score (margin); how much
--   longer than the best an option of a route without a target may be (longer); and how long,
--   from the start of planning, options are looked for (budget_ms). See routing.segment_route.
-- - edit: how far either side of where a route is grabbed an edit may change it, at least
--   window_min_m and window_share times the drag; and how far around that stretch its new way
--   is looked for (area_m). See routing.reroute.
CREATE FUNCTION routing.defaults() RETURNS jsonb
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT '{
        "cost":     {"alpha": 0.7},
        "turns":    {"turn_m": 60, "free_deg": 30, "hairpin_deg": 120, "hairpin_m": 1000},
        "legs":     {"reuse_penalty": 4, "corridor_share": 0.5, "corridor_min_m": 300},
        "area":     {"loop_share": 0.45, "direct_share": 0.5, "min_m": 500},
        "loops":    {
            "sizes": [0.85, 1, 1.15], "ring_low": 0.27, "ring_aim": 0.3, "ring_high": 0.33,
            "bearings": 12, "corner_gap_deg": 60, "bearing_slack_deg": 15, "appeal_steps": 5
        },
        "detours":  {
            "sizes": [0.85, 1, 1.15], "legs_per_ratio": 2, "min_legs": 2, "max_legs": 4,
            "via_reach": 0.3333333333333333,
            "circle_from": 4, "circle_sizes": [0.85, 0.92, 1, 1.08, 1.15],
            "circle_winding": 1.2, "circle_via_deg": 72,
            "single_low": 0.9, "single_aim": 0.95, "single_from": 0.25, "single_to": 0.75,
            "single_per_side": 2
        },
        "evaluate": {"via_turn_deg": 120, "spike_m": 150, "spike_deg": 150, "spike_penalty": 1},
        "doubling": {
            "opposite_deg": 135,
            "close": {"sample_m": 20, "within_m": 40, "apart_m": 300, "run_m": 100, "weight": 1},
            "lobe": {"sample_m": 100, "within_m": 300, "apart_m": 1000, "run_m": 300, "weight": 0.5}
        },
        "score":    {"preference": 0.3, "doubled": 2, "reused": 3},
        "plan":     {
            "tolerance": 0.07, "snap_m": 200, "loop_network": 1,
            "attempts": 2, "kept": 3, "routed": 3
        },
        "options":  {
            "count": 3, "routed": 8, "overlap": 0.5, "margin": 0.15, "longer": 0.25,
            "budget_ms": 10000
        },
        "edit":     {"window_min_m": 300, "window_share": 1.5, "area_m": 1000}
    }'::jsonb
$$;

-- Settings that differ by activity (a ref.activities code), laid over routing.defaults() before
-- a request's own: a turn costs a rider more than a runner, who has no speed to lose at a corner,
-- so rides keep to fewer turns.
CREATE FUNCTION routing.activity_defaults() RETURNS jsonb
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT '{
        "cycling": {"turns": {"turn_m": 180}}
    }'::jsonb
$$;

-- p_defaults with p_overrides laid over it, group by group. An override must name a setting
-- p_defaults has and be of its kind: a number, a non-empty list of numbers, or a group. p_path is
-- where p_defaults sits, for the message. Raises invalid_parameter_value otherwise.
CREATE FUNCTION routing.merge_settings(p_defaults jsonb, p_overrides jsonb, p_path text DEFAULT '')
RETURNS jsonb
LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    v_merged jsonb := p_defaults;
    v_key    text;
    v_value  jsonb;
    v_name   text;
BEGIN
    IF jsonb_typeof(p_overrides) IS DISTINCT FROM 'object' THEN
        RAISE EXCEPTION '% must be an object', coalesce(nullif(p_path, ''), 'settings')
            USING ERRCODE = 'invalid_parameter_value';
    END IF;
    FOR v_key, v_value IN SELECT * FROM jsonb_each(p_overrides) LOOP
        v_name := ltrim(p_path || '.' || v_key, '.');
        IF NOT p_defaults ? v_key THEN
            RAISE EXCEPTION 'unknown setting: %', v_name USING ERRCODE = 'invalid_parameter_value';
        END IF;
        IF jsonb_typeof(p_defaults -> v_key) = 'object' THEN
            v_value := routing.merge_settings(p_defaults -> v_key, v_value, v_name);
        ELSIF jsonb_typeof(v_value) IS DISTINCT FROM jsonb_typeof(p_defaults -> v_key)
            OR (jsonb_typeof(v_value) = 'array' AND (
                jsonb_array_length(v_value) = 0
                OR EXISTS (SELECT 1 FROM jsonb_array_elements(v_value) x
                           WHERE jsonb_typeof(x) <> 'number')
            ))
        THEN
            RAISE EXCEPTION '% must be %', v_name, CASE jsonb_typeof(p_defaults -> v_key)
                WHEN 'array' THEN 'a list of numbers' ELSE 'a number' END
                USING ERRCODE = 'invalid_parameter_value';
        END IF;
        v_merged := jsonb_set(v_merged, ARRAY[v_key], v_value);
    END LOOP;
    RETURN v_merged;
END
$$;

-- What a request asks of each edge and of the planner, checked once by routing.make_profile.
CREATE TYPE routing.profile AS (
    -- a ref.activities code
    activity text,
    -- attribute key -> weight, scaled so the absolute weights sum to 1 (or '{}')
    weights  jsonb,
    -- routing.defaults() with the request's overrides
    settings jsonb
);

-- A number from p_profile's settings: p_name in p_group.
CREATE FUNCTION routing.setting(p_profile routing.profile, p_group text, p_name text)
RETURNS double precision
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT (p_profile.settings -> p_group ->> p_name)::double precision
$$;

-- A list of numbers from p_profile's settings: p_name in p_group.
CREATE FUNCTION routing.settings_list(p_profile routing.profile, p_group text, p_name text)
RETURNS double precision[]
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT ARRAY(
        SELECT x::double precision
        FROM jsonb_array_elements_text(p_profile.settings -> p_group -> p_name) x
    )
$$;

-- Weights run from -1 (avoid) to 1 (prefer) per edge score key, e.g. {"green": 1}. They are
-- scaled so an edge's preference stays in [-1, 1] however many keys are weighted, which keeps
-- cost between (1 - alpha) and (1 + alpha) times length * factor, and so always positive.
-- p_settings overrides routing.defaults() and the activity's routing.activity_defaults(), e.g.
-- {"turns": {"turn_m": 80}}. No setting may be negative, and some have tighter bounds, checked
-- here.
-- Raises invalid_parameter_value for an unknown activity, setting or a value out of range.
CREATE FUNCTION routing.make_profile(
    p_activity text,
    p_weights  jsonb DEFAULT '{}',
    p_settings jsonb DEFAULT '{}'
) RETURNS routing.profile
LANGUAGE plpgsql STABLE AS $$
DECLARE
    v_total   double precision;
    v_profile routing.profile;
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

    SELECT sum(abs(w.value::double precision)) INTO v_total FROM jsonb_each(p_weights) w;
    v_profile := ROW(
        p_activity,
        coalesce(
            (SELECT jsonb_object_agg(w.key, w.value::double precision / v_total)
             FROM jsonb_each(p_weights) w
             WHERE w.value::double precision <> 0),
            '{}'
        ),
        routing.merge_settings(
            routing.merge_settings(
                routing.defaults(), coalesce(routing.activity_defaults() -> p_activity, '{}')
            ),
            p_settings
        )
    )::routing.profile;

    IF jsonb_path_exists(v_profile.settings, 'strict $.**? (@.type() == "number" && @ < 0)') THEN
        RAISE EXCEPTION 'settings must not be negative' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF routing.setting(v_profile, 'cost', 'alpha') >= 1 THEN
        RAISE EXCEPTION 'cost.alpha must be in [0, 1)' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF routing.setting(v_profile, 'legs', 'reuse_penalty') < 1 THEN
        RAISE EXCEPTION 'legs.reuse_penalty must be at least 1'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF routing.setting(v_profile, 'plan', 'tolerance') NOT BETWEEN 1e-9 AND 1 - 1e-9 THEN
        RAISE EXCEPTION 'plan.tolerance must be in (0, 1)'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF routing.setting(v_profile, 'plan', 'snap_m') = 0 THEN
        RAISE EXCEPTION 'plan.snap_m must be positive' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF least(
        routing.setting(v_profile, 'plan', 'attempts'),
        routing.setting(v_profile, 'plan', 'kept'),
        routing.setting(v_profile, 'plan', 'routed')
    ) < 1 THEN
        RAISE EXCEPTION 'plan.attempts, kept and routed must be at least 1'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF routing.setting(v_profile, 'options', 'count') < 1 THEN
        RAISE EXCEPTION 'options.count must be at least 1'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF routing.setting(v_profile, 'options', 'overlap') NOT BETWEEN 1e-9 AND 1 THEN
        RAISE EXCEPTION 'options.overlap must be in (0, 1]'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;
    RETURN v_profile;
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
-- profile's preferences, and multiplied by the reuse penalty (legs.reuse_penalty) on edges in
-- p_used; an edge costs length * factor * (1 - cost.alpha * preference). A missing score counts
-- as 0, so edges that are not scored yet are neither preferred nor avoided.
CREATE FUNCTION routing.cost_sql(
    p_profile routing.profile, p_area geometry, p_used bigint[] DEFAULT '{}'
) RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT routing.edges_sql(
        p_profile.activity,
        format(
            'length_m * factor * (1 - %s * (%s)) * CASE WHEN used THEN %s ELSE 1 END',
            routing.setting(p_profile, 'cost', 'alpha'),
            coalesce(
                (SELECT string_agg(
                     format('%s * coalesce((scores ->> %L)::double precision, 0)', w.value, w.key),
                     ' + ' ORDER BY w.key)
                 FROM jsonb_each(p_profile.weights) w),
                '0'
            ),
            routing.setting(p_profile, 'legs', 'reuse_penalty')
        ),
        p_area,
        p_used
    )
$$;

-- The vertices p_activity can use at most p_max_m metres from p_point, and how far they are. The
-- bounding box keeps the index scan from walking the whole table when nothing is near.
CREATE FUNCTION routing.near_vertices(
    p_activity text, p_point geometry, p_max_m double precision
) RETURNS TABLE (vertex bigint, distance_m double precision)
LANGUAGE sql STABLE AS $$
    SELECT v.id, ST_Distance(v.geom::geography, p_point::geography)
    FROM graph.vertices v
    WHERE v.geom && ST_Buffer(p_point::geography, p_max_m)::geometry
      AND ST_DWithin(v.geom::geography, p_point::geography, p_max_m)
      AND EXISTS (
          SELECT 1 FROM routing.activity_edges e
          WHERE e.activity = p_activity AND (e.source = v.id OR e.target = v.id)
      )
$$;

-- p_points snapped to vertices of p_profile's network in p_area, in order: within plan.snap_m of
-- each point, and all in the same connected part of the network, so that the route can go from
-- one to the next. The part has at least p_min_network_m of edges, which keeps a loop off a
-- path that leads nowhere; of the parts that will do, the one nearest the points (by the sum of
-- the distances) is taken, so a road a little farther away wins over a path cut off from the
-- rest. Directions are ignored, so a part joined only against one-way streets counts as one.
-- p_names says what each point is, such as start, waypoint or finish.
-- Raises no_data_found with DETAIL <name>_off_road, such as start_off_road, for the first point
-- that has no vertex near enough; returns NULL when no part will do.
CREATE FUNCTION routing.snap_points(
    p_profile routing.profile,
    p_area geometry,
    p_points geometry[],
    p_names text[],
    p_min_network_m double precision
) RETURNS bigint[]
LANGUAGE plpgsql AS $$
DECLARE
    v_snap_m  double precision := routing.setting(p_profile, 'plan', 'snap_m');
    v_missing bigint;
    v_snapped bigint[];
BEGIN
    SELECT min(p.i) INTO v_missing
    FROM unnest(p_points) WITH ORDINALITY AS p(geom, i)
    WHERE NOT EXISTS (SELECT 1 FROM routing.near_vertices(p_profile.activity, p.geom, v_snap_m));
    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'no road near the %', p_names[v_missing]
            USING ERRCODE = 'no_data_found', DETAIL = p_names[v_missing] || '_off_road';
    END IF;

    WITH near AS MATERIALIZED (
        SELECT p.i, n.vertex, n.distance_m
        FROM unnest(p_points) WITH ORDINALITY AS p(geom, i),
             routing.near_vertices(p_profile.activity, p.geom, v_snap_m) n
    ),
    parts AS MATERIALIZED (
        SELECT c.node AS vertex, c.component
        FROM pgr_connectedComponents(routing.length_sql(p_profile.activity, p_area)) c
    ),
    placed AS MATERIALIZED (
        SELECT n.i, n.vertex, n.distance_m, p.component
        FROM near n JOIN parts p USING (vertex)
    ),
    -- Only the parts some point is near are measured. An edge counts in the part of its source.
    sizes AS (
        SELECT p.component, sum(e.length_m) AS length_m
        FROM parts p
        JOIN graph.edges e ON e.source = p.vertex
        WHERE p.component IN (SELECT component FROM placed)
          AND p_profile.activity = ANY (e.forward || e.backward)
        GROUP BY p.component
    ),
    chosen AS (
        SELECT n.component
        FROM (
            SELECT component, i, min(distance_m) AS distance_m FROM placed GROUP BY component, i
        ) n
        JOIN sizes s USING (component)
        WHERE s.length_m >= p_min_network_m
        GROUP BY n.component
        HAVING count(*) = cardinality(p_points)
        ORDER BY sum(n.distance_m), n.component
        LIMIT 1
    )
    SELECT array_agg(vertex ORDER BY i) INTO v_snapped
    FROM (
        SELECT DISTINCT ON (p.i) p.i, p.vertex
        FROM placed p JOIN chosen USING (component)
        ORDER BY p.i, p.distance_m, p.vertex
    ) v;
    RETURN v_snapped;
END
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

-- p_sql's network turned into one of arcs, so that a route pays for its turns, as p_profile's
-- turns settings say: moving from one arc to the next costs the next one's cost plus turn_m for a
-- right angle at a junction (a vertex where more than two edges meet), scaled linearly from
-- nothing at free_deg (30) off straight. Bends between two edges are free, since there is no
-- other way to go. A hairpin looks like turning round however many edges meet there, so from
-- hairpin_deg (120) on the cost climbs by up to hairpin_m (1000) more at 180; turning back onto
-- the edge just travelled counts as 180 degrees anywhere.
-- That is more than the reuse penalty adds to most streets, so a route would rather go back over
-- a street it has used than double back on the spot, and does that only when nothing else is
-- left. The ways out of
-- p_departures and into p_arrivals join their departure and arrival nodes; a route may also
-- start from an arc, to carry on from where the last one arrived. The angles come from the ends
-- of each edge's line.
CREATE FUNCTION routing.turns_sql(
    p_sql text, p_profile routing.profile, p_departures bigint[], p_arrivals bigint[]
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
                       %2$s * greatest(m.angle - radians(%5$s), 0) / radians(90 - %5$s)
                           + %6$s * greatest(m.angle - radians(%7$s), 0) / radians(180 - %7$s)
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
        routing.setting(p_profile, 'turns', 'turn_m'),
        coalesce(p_departures, '{}'),
        coalesce(p_arrivals, '{}'),
        routing.setting(p_profile, 'turns', 'free_deg'),
        routing.setting(p_profile, 'turns', 'hairpin_m'),
        routing.setting(p_profile, 'turns', 'hairpin_deg')
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
-- read near the route: loop_share of the target round the start of a loop, and at least min_m
-- (p_settings, the area settings). A route to a finish without a target (p_target_m NULL) keeps
-- within direct_share of their distance of the line between them: the most pleasant way there
-- bends away from the straight line, but not far. With p_waypoints, the points passed on the way
-- in travel order, the area also takes in the way through them: a route of the target through
-- them strays no farther from the straight line between two of them than half of what the
-- target leaves over the straight way through all (direct_share of their distance without a
-- target). The API downloads the tiles covering it before planning, by the default settings.
CREATE FUNCTION routing.search_area(
    p_start geometry,
    p_finish geometry,
    p_target_m double precision,
    p_settings jsonb DEFAULT routing.defaults() -> 'area',
    p_waypoints geometry[] DEFAULT '{}'
) RETURNS geometry
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    WITH ends AS (
        SELECT CASE
            WHEN p_finish IS NULL THEN
                ST_Buffer(
                    p_start::geography,
                    greatest(
                        (p_settings ->> 'loop_share')::double precision * p_target_m,
                        (p_settings ->> 'min_m')::double precision
                    )
                )::geometry
            ELSE
                ST_Buffer(
                    ST_MakeLine(p_start, p_finish)::geography,
                    greatest(
                        coalesce(
                            (p_target_m - ST_Distance(p_start::geography, p_finish::geography)) / 2,
                            (p_settings ->> 'direct_share')::double precision
                                * ST_Distance(p_start::geography, p_finish::geography)
                        ),
                        (p_settings ->> 'min_m')::double precision
                    )
                )::geometry
        END AS area
    ),
    -- Each straight hop of the way through the waypoints.
    hops AS (
        SELECT h.geom, h.next, ST_Distance(h.geom::geography, h.next::geography) AS distance_m
        FROM (
            SELECT w.geom, lead(w.geom) OVER (ORDER BY w.n) AS next
            FROM unnest(p_start || coalesce(p_waypoints, '{}') || coalesce(p_finish, p_start))
                 WITH ORDINALITY AS w(geom, n)
        ) h
        WHERE h.next IS NOT NULL AND coalesce(cardinality(p_waypoints), 0) > 0
    ),
    through AS (
        SELECT ST_Union(ST_Buffer(
                   ST_MakeLine(h.geom, h.next)::geography,
                   greatest(
                       coalesce(
                           (p_target_m - t.distance_m) / 2,
                           (p_settings ->> 'direct_share')::double precision * h.distance_m
                       ),
                       (p_settings ->> 'min_m')::double precision
                   )
               )::geometry) AS area
        FROM hops h, (SELECT sum(distance_m) AS distance_m FROM hops) t
    )
    SELECT coalesce(ST_Union(ends.area, through.area), ends.area) FROM ends, through
$$;

-- A route to try: the vertices it passes in order, from start to finish.
CREATE TYPE routing.candidate AS (
    vias bigint[]
);

-- Loops of about p_goal_m from p_start, as triangles start -> c1 -> c2 -> start. The corners are
-- picked by network distance (a ring at 0.27 to 0.33 of the goal), so the length works out on
-- any street pattern, at 12 bearings with c2 60 degrees after c1, which spreads the loops around
-- the start. Each corner is the most appealing ring vertex within 15 degrees of its bearing (the
-- nearest bearing when there is none), so the preferences choose where the loop goes; appeal is
-- compared in steps of 0.2, and of corners alike in it the one nearest 0.3 of the goal away wins,
-- or every size would take the same most appealing corners. Street patterns stretch some
-- directions more than others, so every loop is also tried 15 % smaller and larger;
-- routing.evaluate scores them all in the same call. The numbers are the loops settings: ring_low,
-- ring_high, bearings, corner_gap_deg, bearing_slack_deg, appeal_steps, ring_aim and sizes.
CREATE FUNCTION routing.loop_candidates(
    p_profile routing.profile, p_area geometry, p_start bigint, p_goal_m double precision
) RETURNS SETOF routing.candidate
LANGUAGE sql AS $$
    WITH s AS MATERIALIZED (
        SELECT routing.setting(p_profile, 'loops', 'ring_low') AS ring_low,
               routing.setting(p_profile, 'loops', 'ring_aim') AS ring_aim,
               routing.setting(p_profile, 'loops', 'ring_high') AS ring_high,
               routing.setting(p_profile, 'loops', 'bearings') AS bearings,
               radians(routing.setting(p_profile, 'loops', 'corner_gap_deg')) AS corner_gap,
               radians(routing.setting(p_profile, 'loops', 'bearing_slack_deg')) AS slack,
               routing.setting(p_profile, 'loops', 'appeal_steps') AS appeal_steps,
               routing.settings_list(p_profile, 'loops', 'sizes') AS sizes
    ),
    band AS MATERIALIZED (
        SELECT d.vertex, d.distance_m
        FROM s, routing.distances(
                 routing.length_sql(p_profile.activity, p_area),
                 p_start,
                 s.ring_high * (SELECT max(k) FROM unnest(s.sizes) k) * p_goal_m
             ) d
        WHERE d.distance_m >= s.ring_low * (SELECT min(k) FROM unnest(s.sizes) k) * p_goal_m
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
             WHERE distance_m BETWEEN s.ring_low * g.goal_m AND s.ring_high * g.goal_m
             ORDER BY routing.angle_between(azimuth, b.bearing) > s.slack,
                      round(appeal * s.appeal_steps) DESC, abs(distance_m - s.ring_aim * g.goal_m),
                      routing.angle_between(azimuth, b.bearing)
             LIMIT 1) AS c1,
            (SELECT vertex FROM ring
             WHERE distance_m BETWEEN s.ring_low * g.goal_m AND s.ring_high * g.goal_m
             ORDER BY routing.angle_between(azimuth, b.bearing + s.corner_gap) > s.slack,
                      round(appeal * s.appeal_steps) DESC, abs(distance_m - s.ring_aim * g.goal_m),
                      routing.angle_between(azimuth, b.bearing + s.corner_gap)
             LIMIT 1) AS c2
        FROM s,
             LATERAL (SELECT radians(i * 360.0 / s.bearings) AS bearing
                      FROM generate_series(0, s.bearings::int - 1) i) b,
             LATERAL (SELECT k * p_goal_m AS goal_m FROM unnest(s.sizes) k) g
    )
    SELECT DISTINCT ROW(ARRAY[p_start, c1, c2, p_start])::routing.candidate
    FROM corners
    WHERE c1 <> c2
$$;

-- The central angle, in radians, of a circular arc that is p_ratio times as long as its chord: the
-- root of angle / (2 sin(angle / 2)) = p_ratio, found by halving. 0 for a ratio of 1 or less;
-- it nears 2 pi, a full circle, as the ratio grows.
CREATE FUNCTION routing.arc_angle(p_ratio double precision) RETURNS double precision
LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL SAFE AS $$
DECLARE
    v_low  double precision := 0;
    v_high double precision := 2 * pi();
    v_mid  double precision;
BEGIN
    IF p_ratio <= 1 THEN
        RETURN 0;
    END IF;
    FOR i IN 1 .. 50 LOOP
        v_mid := (v_low + v_high) / 2;
        IF v_mid / (2 * sin(v_mid / 2)) < p_ratio THEN
            v_low := v_mid;
        ELSE
            v_high := v_mid;
        END IF;
    END LOOP;
    RETURN v_mid;
END
$$;

-- The point p_fraction of the way along a circular arc from p_start to p_finish with central
-- angle p_angle, bulging to the left of the way from start to finish for p_side 1 and to the right
-- for -1. The chord to it from the start is 2 R sin(f a / 2) long and turns (1 - f) a / 2 from the
-- chord to the finish, which an inscribed angle gives.
CREATE FUNCTION routing.arc_point(
    p_start geometry,
    p_finish geometry,
    p_angle double precision,
    p_side integer,
    p_fraction double precision
) RETURNS geometry
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT ST_Project(
        p_start::geography,
        ST_Distance(p_start::geography, p_finish::geography) / (2 * sin(p_angle / 2))
            * 2 * sin(p_fraction * p_angle / 2),
        ST_Azimuth(p_start::geography, p_finish::geography)
            - p_side * (1 - p_fraction) * p_angle / 2
    )::geometry
$$;

-- How far a half ellipse over a chord of length 1 bulges (its semi-minor axis, the semi-major
-- being 1/2) to be p_ratio long, by halving with Ramanujan's perimeter. 0 for a ratio of 1 or less.
CREATE FUNCTION routing.bow_height(p_ratio double precision) RETURNS double precision
LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL SAFE AS $$
DECLARE
    v_low  double precision := 0;
    v_high double precision := p_ratio;
    v_mid  double precision;
BEGIN
    IF p_ratio <= 1 THEN
        RETURN 0;
    END IF;
    FOR i IN 1 .. 50 LOOP
        v_mid := (v_low + v_high) / 2;
        IF pi() / 2 * (3 * (0.5 + v_mid) - sqrt((1.5 + v_mid) * (0.5 + 3 * v_mid))) < p_ratio THEN
            v_low := v_mid;
        ELSE
            v_high := v_mid;
        END IF;
    END LOOP;
    RETURN v_mid;
END
$$;

-- The point p_fraction of the way, by length, along a half ellipse from p_start to p_finish that
-- bulges p_height times their distance to the left of the way from start to finish for p_side 1,
-- and to the right for -1. It leaves the start at a right angle, and never goes behind the start
-- or past the finish. The length is summed over 200 steps of the ellipse's angle.
CREATE FUNCTION routing.bow_point(
    p_start geometry,
    p_finish geometry,
    p_height double precision,
    p_side integer,
    p_fraction double precision
) RETURNS geometry
LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL SAFE AS $$
DECLARE
    v_steps CONSTANT integer := 200;
    v_total double precision := 0;
    v_along double precision := 0;
    v_t     double precision;
    -- In units of the distance from start to finish: x along the way, y to the left.
    v_x     double precision;
    v_y     double precision;
BEGIN
    FOR i IN 1 .. v_steps LOOP
        v_t := pi() * (i - 0.5) / v_steps;
        v_total := v_total + sqrt((0.5 * sin(v_t)) ^ 2 + (p_height * cos(v_t)) ^ 2);
    END LOOP;
    v_t := pi();
    FOR i IN 1 .. v_steps LOOP
        EXIT WHEN v_along >= p_fraction * v_total;
        v_t := pi() * (1 - (i - 0.5) / v_steps);
        v_along := v_along + sqrt((0.5 * sin(v_t)) ^ 2 + (p_height * cos(v_t)) ^ 2);
    END LOOP;
    v_x := 0.5 + 0.5 * cos(v_t);
    v_y := p_side * p_height * sin(v_t);
    RETURN ST_Project(
        p_start::geography,
        sqrt(v_x ^ 2 + v_y ^ 2) * ST_Distance(p_start::geography, p_finish::geography),
        ST_Azimuth(p_start::geography, p_finish::geography) - atan2(v_y, v_x)
    )::geometry;
END
$$;

-- Routes of about p_goal_m from p_start to p_finish, picked by network distance from the start
-- (d_start) and to the finish (d_finish):
-- - the direct route;
-- - bows: the route follows half an ellipse from start to finish, on either side, as long as the
--   goal: a flat bow for a goal a little beyond the direct route, a tall U for a long one. It
--   never goes behind the start or past the finish. Streets wind, so the bow is shortened by the
--   ratio of the direct route to the straight line. Its vias are spread evenly along it, one to
--   three, about two legs per multiple of the direct route, so the route keeps to the curve; each
--   is the most appealing vertex within a third of the spacing of its point (the nearest when
--   there is none);
-- - start -> c -> finish through the two most appealing vertices on each side with d_start +
--   d_finish just under the goal, beside the middle half of the way from start to finish, so
--   that c is neither behind the start nor past the finish;
-- - for a goal four times the direct route or more, where a bow would be a tall narrow U, a
--   circle through start and finish, the long way round: a loop that passes the finish, not one
--   that comes back to the start first. Its vias are chosen as a bow's, one per 72 degrees.
-- Every shape is tried at three sizes, as in routing.loop_candidates. The numbers are the detours
-- settings: legs_per_ratio, min_legs and max_legs for a bow's legs, via_reach for how far from
-- its point a via may be, as a share of the spacing; circle_from, circle_winding, circle_via_deg
-- and circle_sizes for circles; single_low, single_aim, single_from, single_to and
-- single_per_side for single detours, and sizes.
CREATE FUNCTION routing.detour_candidates(
    p_profile routing.profile,
    p_area geometry,
    p_start bigint,
    p_finish bigint,
    p_goal_m double precision
) RETURNS SETOF routing.candidate
LANGUAGE sql AS $$
    WITH s AS MATERIALIZED (
        SELECT routing.settings_list(p_profile, 'detours', 'sizes') AS sizes,
               routing.setting(p_profile, 'detours', 'legs_per_ratio') AS legs_per_ratio,
               routing.setting(p_profile, 'detours', 'min_legs') AS min_legs,
               routing.setting(p_profile, 'detours', 'max_legs') AS max_legs,
               routing.setting(p_profile, 'detours', 'via_reach') AS via_reach,
               routing.setting(p_profile, 'detours', 'circle_from') AS circle_from,
               routing.settings_list(p_profile, 'detours', 'circle_sizes') AS circle_sizes,
               routing.setting(p_profile, 'detours', 'circle_winding') AS circle_winding,
               radians(routing.setting(p_profile, 'detours', 'circle_via_deg')) AS circle_via,
               routing.setting(p_profile, 'detours', 'single_low') AS single_low,
               routing.setting(p_profile, 'detours', 'single_aim') AS single_aim,
               routing.setting(p_profile, 'detours', 'single_from') AS single_from,
               routing.setting(p_profile, 'detours', 'single_to') AS single_to,
               routing.setting(p_profile, 'detours', 'single_per_side') AS single_per_side
    ),
    -- The largest goal any shape is tried at, which bounds every search.
    reach_m AS MATERIALIZED (
        SELECT p_goal_m * greatest(
            (SELECT max(k) FROM unnest(s.sizes) k), (SELECT max(k) FROM unnest(s.circle_sizes) k)
        ) AS max_m
        FROM s
    ),
    ends AS (
        SELECT s.geom AS start_geom, f.geom AS finish_geom,
               ST_Distance(s.geom::geography, f.geom::geography) AS straight_m
        FROM graph.vertices s, graph.vertices f
        WHERE s.id = p_start AND f.id = p_finish
    ),
    goals AS (
        SELECT k * p_goal_m AS goal_m FROM s, unnest(s.sizes) k
    ),
    from_start AS (
        SELECT d.* FROM reach_m, routing.distances(
            routing.length_sql(p_profile.activity, p_area), p_start, reach_m.max_m
        ) d
    ),
    to_finish AS (
        SELECT d.* FROM reach_m, routing.distances(
            routing.reversed_sql(routing.length_sql(p_profile.activity, p_area)),
            p_finish,
            reach_m.max_m
        ) d
    ),
    direct AS (
        SELECT distance_m FROM to_finish WHERE vertex = p_start
    ),
    -- Vertices on some route of at most the largest goal; the stats are read for these alone.
    near AS MATERIALIZED (
        SELECT s.vertex, s.distance_m AS d_start, f.distance_m AS d_finish
        FROM from_start s JOIN to_finish f USING (vertex) CROSS JOIN reach_m
        WHERE s.vertex NOT IN (p_start, p_finish)
          AND s.distance_m + f.distance_m <= reach_m.max_m
    ),
    reach AS MATERIALIZED (
        SELECT n.vertex, n.d_start, n.d_finish, v.geom, a.from_start, a.axis,
               -- How far along the way from start to finish the vertex lies, from 0 to 1.
               ST_Distance(ends.start_geom::geography, v.geom::geography)
                   * cos(a.from_start - a.axis) / ends.straight_m AS along,
               st.appeal
        FROM near n
        JOIN routing.vertex_stats(p_profile, ARRAY(SELECT vertex FROM near)) st USING (vertex)
        JOIN graph.vertices v ON v.id = n.vertex
        CROSS JOIN ends
        -- On the ellipsoid: in degrees, east and west are stretched by 1 / cos(latitude).
        CROSS JOIN LATERAL (
            SELECT ST_Azimuth(ends.start_geom::geography, ends.finish_geom::geography) AS axis,
                   ST_Azimuth(ends.start_geom::geography, v.geom::geography) AS from_start
        ) a
        WHERE st.degree > 1 AND ends.straight_m > 0
    ),
    -- Bows, and circles for long goals: per shape and side, its points and how far apart.
    shapes AS (
        -- Streets wind: a shape is shortened by how much longer the direct route is than the
        -- straight line. Measured against the straight distance, it is then goal / direct long.
        SELECT g.goal_m, side, 'bow' AS kind,
               routing.bow_height(g.goal_m / direct.distance_m) AS size,
               least(s.max_legs, greatest(
                   s.min_legs, round(s.legs_per_ratio * g.goal_m / direct.distance_m)
               ))::int AS legs,
               g.goal_m / direct.distance_m * ends.straight_m AS length_m
        FROM s, goals g, direct, ends, unnest(ARRAY[1, -1]) side
        WHERE g.goal_m > direct.distance_m AND ends.straight_m > 0
        UNION ALL
        -- A circle winds through the streets even where the direct route runs straight, so it is
        -- shortened by 1.2 at least. Its vias are far apart, so its length jumps between sizes:
        -- it gets two more.
        SELECT g.goal_m, side, 'circle',
               routing.arc_angle(g.goal_m / w.winding_m),
               ceil(routing.arc_angle(g.goal_m / w.winding_m) / s.circle_via)::int,
               g.goal_m / w.winding_m * ends.straight_m
        FROM s, LATERAL (SELECT k * p_goal_m AS goal_m FROM unnest(s.circle_sizes) k) g,
             direct, ends, unnest(ARRAY[1, -1]) side,
             LATERAL (
                 SELECT greatest(direct.distance_m, s.circle_winding * ends.straight_m) AS winding_m
             ) w
        WHERE p_goal_m >= s.circle_from * direct.distance_m AND ends.straight_m > 0
    ),
    -- Materialized, so each point is worked out once, not again for every vertex it is compared
    -- with.
    shape_points AS MATERIALIZED (
        SELECT sh.goal_m, sh.side, sh.kind, k,
               CASE sh.kind
                   WHEN 'bow' THEN routing.bow_point(
                       ends.start_geom, ends.finish_geom, sh.size, sh.side, k::float8 / sh.legs)
                   ELSE routing.arc_point(
                       ends.start_geom, ends.finish_geom, sh.size, sh.side, k::float8 / sh.legs)
               END AS point,
               sh.length_m / sh.legs * s.via_reach AS radius_m
        FROM shapes sh CROSS JOIN ends CROSS JOIN s
        CROSS JOIN LATERAL generate_series(1, sh.legs - 1) k
    ),
    shape_vias AS (
        SELECT p.goal_m, p.side, p.kind, p.k,
               (SELECT r.vertex FROM reach r
                ORDER BY NOT ST_DWithin(r.geom::geography, p.point::geography, p.radius_m),
                         r.appeal DESC,
                         r.geom <-> p.point
                LIMIT 1) AS vertex
        FROM shape_points p
    ),
    shape_routes AS (
        SELECT array_agg(vertex ORDER BY k) AS vias
        FROM shape_vias
        GROUP BY goal_m, side, kind
        HAVING count(vertex) = count(*)
    ),
    single AS (
        SELECT reach.vertex, row_number() OVER (
            PARTITION BY goals.goal_m, sign(sin(from_start - axis))
            ORDER BY appeal DESC, abs(d_start + d_finish - s.single_aim * goals.goal_m)
        ) AS rank
        FROM s CROSS JOIN reach
        JOIN goals ON d_start + d_finish BETWEEN s.single_low * goal_m AND goal_m
        WHERE along BETWEEN s.single_from AND s.single_to
    )
    SELECT ROW(ARRAY[p_start, p_finish])::routing.candidate
    UNION
    SELECT ROW(p_start || vias || p_finish)::routing.candidate FROM shape_routes
    UNION
    SELECT ROW(ARRAY[p_start, vertex, p_finish])::routing.candidate
    FROM s, single WHERE rank <= s.single_per_side
$$;

-- How much of p_line, in metres, comes back alongside itself, heading the other way (more than
-- 135 degrees apart), by the larger of two measures, a lobe counting half since it is not as bad
-- as going back over the same way:
-- - within 40 m of a part at least 300 m further along, for runs of 100 m or more, sampled every
--   20 m at most: the same streets, a road and the cycle path beside it, a spike;
-- - within 300 m of a part at least 1000 m further along, for runs of 300 m or more, sampled
--   every 100 m at most, which a lobe does not need finer: out on one path and back on another.
-- Where the line crosses itself, or two sides of a loop meet at a corner, they head apart, not
-- back, and a round loop's sides are farther apart. Samples are put in cells as wide as the
-- distance, so that a sample's matches are in its own cell or a neighbouring one. The line is
-- measured in Web Mercator scaled by cos(latitude), which is true to well under a percent over a
-- route. A closed line is measured round the loop, so its end is not taken for a return to its
-- start. The numbers are p_settings, the doubling settings: opposite_deg, and a group per rule.
CREATE FUNCTION routing.doubled_m(
    p_line geometry, p_settings jsonb DEFAULT routing.defaults() -> 'doubling'
) RETURNS double precision
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    WITH rules AS (
        SELECT r.key AS rule,
               (r.value ->> 'sample_m')::double precision AS sample_m,
               (r.value ->> 'within_m')::double precision AS within_m,
               (r.value ->> 'apart_m')::double precision AS apart_m,
               (r.value ->> 'run_m')::double precision AS run_m,
               (r.value ->> 'weight')::double precision AS weight,
               radians((p_settings ->> 'opposite_deg')::double precision) AS opposite
        FROM jsonb_each(p_settings) r
        WHERE jsonb_typeof(r.value) = 'object'
    ),
    -- Materialized, like total below: inlined, it would be worked out again for every sample.
    line AS MATERIALIZED (
        SELECT ST_Transform(p_line, 3857) AS g, cos(radians(ST_Y(ST_Centroid(p_line)))) AS k
    ),
    pts AS (
        SELECT r.rule, (dp).path[1] AS i, ST_X((dp).geom) * line.k AS x,
               ST_Y((dp).geom) * line.k AS y
        FROM rules r, line, ST_DumpPoints(ST_Segmentize(line.g, r.sample_m / line.k)) dp
    ),
    steps AS (
        SELECT rule, i, x, y,
               coalesce(sqrt((x - lag(x) OVER w) ^ 2 + (y - lag(y) OVER w) ^ 2), 0) AS step_m,
               atan2(x - lag(x) OVER w, y - lag(y) OVER w) AS heading
        FROM pts WINDOW w AS (PARTITION BY rule ORDER BY i)
    ),
    along AS (
        SELECT rule, i, x, y, step_m, heading,
               sum(step_m) OVER (PARTITION BY rule ORDER BY i) AS along_m
        FROM steps
    ),
    -- Inlined, this would be summed again for every pair of samples compared.
    total AS MATERIALIZED (
        SELECT max(along_m) AS length_m, ST_IsClosed(p_line) AS closed FROM along
    ),
    cells AS MATERIALIZED (
        SELECT a.rule, r.within_m, r.apart_m, r.opposite, a.i, a.x, a.y, a.heading, a.along_m,
               floor(a.x / r.within_m)::bigint AS cx, floor(a.y / r.within_m)::bigint AS cy
        FROM along a JOIN rules r USING (rule)
        WHERE a.step_m > 0
    ),
    -- Each sample with the nine cells to look in, so that the match is a join on equal keys,
    -- which is hashed, rather than every sample against every other.
    looks AS MATERIALIZED (
        SELECT c.*, c.cx + dx AS kx, c.cy + dy AS ky
        FROM cells c, generate_series(-1, 1) dx, generate_series(-1, 1) dy
    ),
    near AS (
        SELECT DISTINCT a.rule, a.i
        FROM looks a
        JOIN cells b ON b.rule = a.rule AND b.cx = a.kx AND b.cy = a.ky
        CROSS JOIN total t
        WHERE CASE WHEN t.closed
                   THEN least(abs(a.along_m - b.along_m), t.length_m - abs(a.along_m - b.along_m))
                   ELSE abs(a.along_m - b.along_m)
              END > a.apart_m
          AND (a.x - b.x) ^ 2 + (a.y - b.y) ^ 2 <= a.within_m ^ 2
          AND routing.angle_between(a.heading, b.heading) > a.opposite
    ),
    -- Consecutive samples share a run: their index less their rank is the same.
    runs AS (
        SELECT n.rule, a.step_m, n.i - row_number() OVER (PARTITION BY n.rule ORDER BY n.i) AS run
        FROM near n JOIN along a USING (rule, i)
    ),
    measures AS (
        SELECT u.rule, r.weight * sum(u.run_m) AS doubled_m
        FROM (SELECT rule, run, sum(step_m) AS run_m FROM runs GROUP BY rule, run) u
        JOIN rules r USING (rule)
        WHERE u.run_m >= r.run_m
        GROUP BY u.rule, r.weight
    )
    SELECT coalesce(max(doubled_m), 0) FROM measures
$$;

-- How well a route of p_length_m fits, lower is better: the share by which it misses the target,
-- 0.3 per unit of length-weighted preference below 1, twice the share that is doubled (see
-- routing.doubled_m), so that going out and back scores worse than missing the target by as much,
-- and three times more the share on edges travelled more than once (p_reused_m). Going back over
-- the same edges is the worst of all, and short stretches of it, such as into a side street and
-- out again, are too near along the route for routing.doubled_m to see. The weights are
-- p_settings, the score settings: preference, doubled and reused.
CREATE FUNCTION routing.score(
    p_target_m   double precision,
    p_length_m   double precision,
    p_preference double precision,
    p_doubled_m  double precision,
    p_reused_m   double precision,
    p_settings   jsonb DEFAULT routing.defaults() -> 'score'
) RETURNS double precision
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT abs(p_length_m - p_target_m) / p_target_m
        + (p_settings ->> 'preference')::double precision * (1 - coalesce(p_preference, 0))
        + (p_settings ->> 'doubled')::double precision
            * coalesce(p_doubled_m / nullif(p_length_m, 0), 0)
        + (p_settings ->> 'reused')::double precision
            * coalesce(p_reused_m / nullif(p_length_m, 0), 0)
$$;

-- A candidate as pgRouting routes it: its length, length-weighted preference, length that is
-- doubled (see routing.doubled_m), and a score where lower is better.
CREATE TYPE routing.evaluation AS (
    vias       bigint[],
    length_m   double precision,
    preference double precision,
    doubled_m  double precision,
    score      double precision
);

-- Every candidate evaluated from one pgr_dijkstra call over the distinct legs of all of them, on
-- routing.turns_sql's network so that turns count as they will on the route. Legs are found apart,
-- so a leg does not know how the one before arrived; where its cheapest way out of the via turns
-- back sharply (more than via_turn_deg, 120 degrees, where a hairpin starts to cost) from the way
-- the last leg came in, it is found again from that arc, in one more call for all such legs, as
-- routing.route_edges will route it. The score is routing.score, plus spike_penalty (1) when the
-- route still has to turn back at a via (one at the end of a spur, or where every way on is a
-- hairpin), or turns round there by more than spike_deg (150) over the spike_m (150 m) either
-- side, which only a route with no other candidate takes; these are the evaluate settings.
-- Legs are evaluated without the reuse penalty that the final route gets, so a leg may double
-- back where the route will not. Candidates with a leg that cannot be travelled are left out.
-- p_before is the route so far when the candidates carry it on (as routing.route_json gives it):
-- going back over its edges counts as reused, and coming back alongside it as doubled, though
-- neither its length nor what it already doubles counts.
CREATE FUNCTION routing.evaluate(
    p_profile routing.profile,
    p_area geometry,
    p_target_m double precision,
    p_candidates routing.candidate[],
    p_before jsonb DEFAULT NULL
) RETURNS SETOF routing.evaluation
LANGUAGE sql AS $$
    WITH before AS MATERIALIZED (
        SELECT b.line, routing.doubled_m(b.line, p_profile.settings -> 'doubling') AS doubled_m
        FROM (SELECT ST_GeomFromGeoJSON(p_before -> 'geometry') AS line) b
        WHERE p_before IS NOT NULL
    ),
    before_edges AS (
        SELECT DISTINCT e::bigint AS id FROM jsonb_array_elements_text(p_before -> 'edges') e
    ),
    candidates AS (
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
                routing.cost_sql(p_profile, p_area), p_profile, pairs.sources, pairs.targets
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
        WHERE routing.turn_angle(ea.last_arc, eb.first_arc)
            > radians(routing.setting(p_profile, 'evaluate', 'via_turn_deg'))
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
                routing.cost_sql(p_profile, p_area), p_profile, '{}', t.targets
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
        WHERE routing.turn_angle(t.from_arc, r.arc)
              > radians(routing.setting(p_profile, 'evaluate', 'via_turn_deg'))
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
    -- Every leg's arcs in order: redone where it turned back, otherwise as first found.
    leg_arcs AS (
        SELECT l.n, l.i, p.path_seq AS seq, p.arc
        FROM legs l
        JOIN paths p ON p.source = l.source AND p.target = l.target
        WHERE NOT EXISTS (SELECT 1 FROM turning t WHERE t.n = l.n AND t.i = l.i)
        UNION ALL
        SELECT t.n, t.i, r.path_seq, r.arc
        FROM turning t
        JOIN redone r ON r.from_arc = t.from_arc AND r.target = t.target
    ),
    steps AS MATERIALIZED (
        SELECT a.n, a.i, a.seq,
               CASE WHEN a.arc % 2 = 0 THEN e.source ELSE e.target END AS tail,
               CASE WHEN a.arc % 2 = 0 THEN e.target ELSE e.source END AS head,
               sum(e.length_m) OVER (PARTITION BY a.n, a.i ORDER BY a.seq) AS done_m,
               sum(e.length_m) OVER (PARTITION BY a.n, a.i ORDER BY a.seq DESC) AS left_m
        FROM leg_arcs a JOIN graph.edges e ON e.id = a.arc / 2
    ),
    spike AS (SELECT routing.setting(p_profile, 'evaluate', 'spike_m') AS m),
    -- Where each leg is spike_m before its end and after its start, or at its other end when it is
    -- shorter.
    leg_reach AS (
        SELECT b.n, b.i, b.tail AS before_end, a.head AS after_start
        FROM (
            SELECT DISTINCT ON (n, i) n, i, tail FROM steps, spike
            ORDER BY n, i, left_m < spike.m,
                     CASE WHEN left_m >= spike.m THEN left_m ELSE -left_m END
        ) b
        JOIN (
            SELECT DISTINCT ON (n, i) n, i, head FROM steps, spike
            ORDER BY n, i, done_m < spike.m,
                     CASE WHEN done_m >= spike.m THEN done_m ELSE -done_m END
        ) a USING (n, i)
    ),
    -- Vias the route turns round at over the spike_m either side, as round a block, though no
    -- single turn there is sharp and the ways back are too far apart to count as doubled.
    spikes AS (
        SELECT DISTINCT f.n
        FROM follows f
        JOIN legs l ON l.n = f.n AND l.i = f.before
        JOIN leg_reach rb ON rb.n = f.n AND rb.i = f.before
        JOIN leg_reach ra ON ra.n = f.n AND ra.i = f.after
        JOIN graph.vertices p ON p.id = rb.before_end
        JOIN graph.vertices v ON v.id = l.target
        JOIN graph.vertices q ON q.id = ra.after_start
        WHERE p.id <> v.id AND q.id <> v.id
          AND routing.angle_between(
                  ST_Azimuth(p.geom::geography, v.geom::geography),
                  ST_Azimuth(v.geom::geography, q.geom::geography)
              ) > radians(routing.setting(p_profile, 'evaluate', 'spike_deg'))
    ),
    -- Each candidate's line in travel order, for measuring how much of it is doubled.
    lines AS (
        SELECT l.n,
               ST_MakeLine(
                   CASE WHEN l.arc % 2 = 0 THEN e.geom ELSE ST_Reverse(e.geom) END
                   ORDER BY l.i, l.seq
               ) AS line
        FROM leg_arcs l
        JOIN complete USING (n)
        JOIN graph.edges e ON e.id = l.arc / 2
        GROUP BY l.n
    ),
    -- Measured once a candidate; the joins below could otherwise measure it again.
    doubled AS MATERIALIZED (
        SELECT l.n,
               CASE WHEN b.line IS NULL
                   THEN routing.doubled_m(l.line, p_profile.settings -> 'doubling')
                   ELSE greatest(
                       routing.doubled_m(
                           ST_MakeLine(b.line, l.line), p_profile.settings -> 'doubling'
                       ) - b.doubled_m,
                       0
                   )
               END AS doubled_m
        FROM lines l LEFT JOIN before b ON true
    ),
    uses AS (
        SELECT l.n, l.arc / 2 AS edge, count(*) AS times
        FROM leg_arcs l
        JOIN complete USING (n)
        GROUP BY l.n, l.arc / 2
    ),
    totals AS (
        SELECT
            u.n,
            sum(e.length_m * u.times) AS length_m,
            sum(e.length_m * u.times * routing.preference(p_profile.weights, e.scores))
                AS preferred_m,
            sum(e.length_m * (u.times - 1 + CASE WHEN b.id IS NULL THEN 0 ELSE 1 END))
                AS reused_m
        FROM uses u
        JOIN graph.edges e ON e.id = u.edge
        LEFT JOIN before_edges b ON b.id = u.edge
        GROUP BY u.n
    )
    SELECT ROW(
        c.vias,
        t.length_m,
        t.preferred_m / nullif(t.length_m, 0),
        d.doubled_m,
        routing.score(
            p_target_m, t.length_m, t.preferred_m / nullif(t.length_m, 0), d.doubled_m, t.reused_m,
            p_profile.settings -> 'score'
        ) + CASE WHEN r.n IS NULL AND s.n IS NULL THEN 0
                 ELSE routing.setting(p_profile, 'evaluate', 'spike_penalty') END
    )::routing.evaluation
    FROM totals t
    JOIN candidates c USING (n)
    JOIN doubled d USING (n)
    LEFT JOIN turning_round r USING (n)
    LEFT JOIN spikes s USING (n)
$$;

-- The edges of the route through p_vias in travel order, with the vertex each is entered from.
-- Legs are routed one after another on routing.turns_sql's network, each with the edges before it
-- in p_used, so the reuse penalty keeps a leg off the streets the route has already taken where
-- it can. Each leg after the first starts from the arc the last one arrived by, so the turn at a
-- via costs what any other turn does and the route does not double back there. A leg is routed
-- in a corridor first, corridor_share (half) as wide as its vias are apart and at least
-- corridor_min_m (300 m), which holds far fewer edges than the whole area; only when it has no way
-- through is the whole area searched. Edges in p_avoid pay the reuse penalty from the start.
-- Raises no_data_found (detail unreachable) when a leg cannot be travelled.
CREATE FUNCTION routing.route_edges(
    p_profile routing.profile, p_area geometry, p_vias bigint[], p_avoid bigint[] DEFAULT '{}'
) RETURNS TABLE (step integer, vertex bigint, edge_id bigint)
LANGUAGE plpgsql AS $$
DECLARE
    v_used     bigint[] := p_avoid;
    -- The departure node of the first leg, then the arc each leg arrived by.
    v_from     bigint := routing.departure(p_vias[1]);
    v_arcs     bigint[];
    v_step     integer := 0;
    v_corridor geometry;
    v_leg_area geometry;
BEGIN
    FOR i IN 1 .. cardinality(p_vias) - 1 LOOP
        CONTINUE WHEN p_vias[i] = p_vias[i + 1];
        SELECT ST_Buffer(
                   ST_MakeLine(a.geom, b.geom)::geography,
                   greatest(
                       ST_Distance(a.geom::geography, b.geom::geography)
                           * routing.setting(p_profile, 'legs', 'corridor_share'),
                       routing.setting(p_profile, 'legs', 'corridor_min_m')
                   )
               )::geometry
        INTO v_corridor
        FROM graph.vertices a, graph.vertices b
        WHERE a.id = p_vias[i] AND b.id = p_vias[i + 1];
        IF p_area IS NOT NULL THEN
            v_corridor := ST_Intersection(v_corridor, p_area);
        END IF;
        FOREACH v_leg_area IN ARRAY ARRAY[v_corridor, p_area] LOOP
            SELECT array_agg(d.node ORDER BY d.seq) INTO v_arcs
            FROM pgr_dijkstra(
                routing.turns_sql(
                    routing.cost_sql(p_profile, v_leg_area, v_used),
                    p_profile,
                    CASE WHEN i = 1 THEN ARRAY[p_vias[1]] END,
                    ARRAY[p_vias[i + 1]]
                ),
                v_from,
                routing.arrival(p_vias[i + 1])
            ) d
            -- The arc the leg starts from was travelled by the leg before.
            WHERE d.node >= 0 AND d.node <> v_from;
            EXIT WHEN v_arcs IS NOT NULL;
        END LOOP;
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

-- How a route along p_edge_ids (in travel order; an edge travelled twice counts twice) scores, as
-- the API and saved routes describe it: per score key, the mean over the length that has the key,
-- and the share of the route's length that has it (coverage), both to four decimals. Keys no edge
-- has are left out.
CREATE FUNCTION routing.route_scores(p_edge_ids bigint[]) RETURNS jsonb
LANGUAGE sql STABLE AS $$
    WITH legs AS (
        SELECT e.length_m, e.scores
        FROM unnest(p_edge_ids) AS s (id)
        JOIN graph.edges e ON e.id = s.id
    ),
    total AS (
        SELECT sum(length_m) AS length_m FROM legs
    ),
    scored AS (
        SELECT kv.key, sum(l.length_m * kv.value::float8) AS weighted, sum(l.length_m) AS length_m
        FROM legs l
        CROSS JOIN LATERAL jsonb_each(l.scores) kv
        GROUP BY kv.key
    )
    SELECT coalesce(
        jsonb_object_agg(s.key, jsonb_build_object(
            'mean', round((s.weighted / s.length_m)::numeric, 4),
            'coverage', round((s.length_m / total.length_m)::numeric, 4)
        )) FILTER (WHERE s.length_m > 0),
        '{}'
    )
    FROM scored s, total
$$;

-- The route through p_vias as the planner works with it: the line in travel order, its length,
-- the length-weighted share of every edge score along it, the length travelled more than once,
-- the edge ids in order, whether each is travelled from its source to its target (forward), and
-- p_warnings. p_avoid is passed on to routing.route_edges. routing.route_out turns it into what
-- the API returns.
CREATE FUNCTION routing.route_json(
    p_profile routing.profile,
    p_area geometry,
    p_vias bigint[],
    p_warnings text[],
    p_avoid bigint[] DEFAULT '{}'
) RETURNS jsonb
LANGUAGE sql AS $$
    WITH path AS MATERIALIZED (
        SELECT
            r.step,
            e.id,
            e.length_m,
            e.scores,
            r.vertex = e.source AS forward,
            -- pgRouting gives the vertex an edge is entered from; turn the rest around.
            CASE WHEN r.vertex = e.source THEN e.geom ELSE ST_Reverse(e.geom) END AS geom
        FROM routing.route_edges(p_profile, p_area, p_vias, p_avoid) r
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
        'forward', (SELECT to_jsonb(array_agg(forward ORDER BY step)) FROM path),
        'warnings', to_jsonb(p_warnings)
    )
    FROM total, shares, reused
$$;

-- The order to travel p_path in with p_points put in, as indexes into p_path || p_points: each
-- point in turn goes where it lengthens the way least by straight distance (cheapest insertion).
-- p_path keeps its order and its ends stay the ends, so it needs two points at least.
CREATE FUNCTION routing.insertion_order(p_path geometry[], p_points geometry[])
RETURNS integer[]
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
DECLARE
    v_all   geometry[] := p_path || p_points;
    v_order integer[] := ARRAY(SELECT generate_series(1, cardinality(p_path)));
    v_point integer;
    v_at    integer;
BEGIN
    FOR k IN 1 .. coalesce(cardinality(p_points), 0) LOOP
        v_point := cardinality(p_path) + k;
        SELECT i INTO v_at
        FROM generate_series(1, cardinality(v_order) - 1) i
        ORDER BY ST_Distance(v_all[v_order[i]]::geography, v_all[v_point]::geography)
                 + ST_Distance(v_all[v_point]::geography, v_all[v_order[i + 1]]::geography)
                 - ST_Distance(v_all[v_order[i]]::geography, v_all[v_order[i + 1]]::geography),
                 i
        LIMIT 1;
        v_order := v_order[1:v_at] || v_point || v_order[v_at + 1:];
    END LOOP;
    RETURN v_order;
END
$$;

-- Waypoints as routing.plan_route takes them, checked: a JSON array of objects with lon and lat,
-- and at, where on the route the waypoint should be: "any" (the default) wherever it suits,
-- "asap" as soon as possible, or "after" after about after_m metres. In the order given.
-- Raises invalid_parameter_value for anything else.
CREATE FUNCTION routing.read_waypoints(p_waypoints jsonb)
RETURNS TABLE (n integer, geom geometry, at text, after_m double precision)
LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    v_waypoint jsonb;
    v_at       text;
BEGIN
    IF jsonb_typeof(p_waypoints) IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'waypoints must be an array' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    FOR i IN 0 .. jsonb_array_length(p_waypoints) - 1 LOOP
        v_waypoint := p_waypoints -> i;
        v_at := coalesce(v_waypoint ->> 'at', 'any');
        IF jsonb_typeof(v_waypoint) IS DISTINCT FROM 'object'
            OR v_waypoint - ARRAY['lon', 'lat', 'at', 'after_m'] <> '{}'
            OR jsonb_typeof(v_waypoint -> 'lon') IS DISTINCT FROM 'number'
            OR jsonb_typeof(v_waypoint -> 'lat') IS DISTINCT FROM 'number'
            OR abs((v_waypoint ->> 'lon')::double precision) > 180
            OR abs((v_waypoint ->> 'lat')::double precision) > 90
        THEN
            RAISE EXCEPTION 'waypoint % must be an object of lon, lat, at and after_m', i + 1
                USING ERRCODE = 'invalid_parameter_value';
        END IF;
        IF v_at NOT IN ('any', 'asap', 'after') THEN
            RAISE EXCEPTION 'waypoint % must be at any, asap or after', i + 1
                USING ERRCODE = 'invalid_parameter_value';
        END IF;
        IF (v_at = 'after') <> (v_waypoint ? 'after_m')
            OR (v_at = 'after' AND (
                jsonb_typeof(v_waypoint -> 'after_m') IS DISTINCT FROM 'number'
                OR (v_waypoint ->> 'after_m')::double precision <= 0
            ))
        THEN
            RAISE EXCEPTION 'waypoint % needs a positive after_m if, and only if, at after',
                i + 1 USING ERRCODE = 'invalid_parameter_value';
        END IF;
        n := i + 1;
        geom := ST_Point(
            (v_waypoint ->> 'lon')::double precision, (v_waypoint ->> 'lat')::double precision, 4326
        );
        at := v_at;
        after_m := (v_waypoint ->> 'after_m')::double precision;
        RETURN NEXT;
    END LOOP;
END
$$;

-- The points a route from p_start to p_end passes, in travel order (k, from 1), with what each
-- is (kind: start, asap, after, any or end), after_m for after waypoints, and n, the waypoint's
-- place in p_waypoints (from 1; NULL for the start and end): the start and the asap waypoints in
-- the order given, then the after waypoints by after_m and the end, with the any waypoints put in
-- among them where they lengthen the way least (see routing.insertion_order). The waypoints are
-- as routing.read_waypoints takes them.
CREATE FUNCTION routing.travel_points(p_start geometry, p_end geometry, p_waypoints jsonb)
RETURNS TABLE (k integer, geom geometry, kind text, after_m double precision, n integer)
LANGUAGE plpgsql STABLE AS $$
#variable_conflict use_column
DECLARE
    v_points    geometry[];
    v_kinds     text[];
    v_after_m   double precision[];
    v_ns        integer[];
    v_tail      geometry[];
    v_tail_kind text[];
    v_tail_m    double precision[];
    v_tail_n    integer[];
    v_any       geometry[];
    v_any_n     integer[];
BEGIN
    -- The start and the asap waypoints, then the after waypoints and the end with the any
    -- waypoints put in among them.
    SELECT ARRAY[p_start] || coalesce(array_agg(w.geom ORDER BY w.n), '{}'),
           ARRAY['start'] || coalesce(array_agg(w.at ORDER BY w.n), '{}'),
           ARRAY[NULL::double precision] || coalesce(array_agg(w.after_m ORDER BY w.n), '{}'),
           ARRAY[NULL::integer] || coalesce(array_agg(w.n ORDER BY w.n), '{}')
    INTO v_points, v_kinds, v_after_m, v_ns
    FROM routing.read_waypoints(p_waypoints) w
    WHERE w.at = 'asap';
    SELECT ARRAY[v_points[cardinality(v_points)]]
               || coalesce(array_agg(w.geom ORDER BY w.after_m, w.n), '{}') || p_end,
           ARRAY['from'] || coalesce(array_agg(w.at ORDER BY w.after_m, w.n), '{}') || 'end'::text,
           ARRAY[NULL::double precision]
               || coalesce(array_agg(w.after_m ORDER BY w.after_m, w.n), '{}')
               || NULL::double precision,
           ARRAY[NULL::integer] || coalesce(array_agg(w.n ORDER BY w.after_m, w.n), '{}')
               || NULL::integer
    INTO v_tail, v_tail_kind, v_tail_m, v_tail_n
    FROM routing.read_waypoints(p_waypoints) w
    WHERE w.at = 'after';
    SELECT coalesce(array_agg(w.geom ORDER BY w.n), '{}'),
           coalesce(array_agg(w.n ORDER BY w.n), '{}')
    INTO v_any, v_any_n
    FROM routing.read_waypoints(p_waypoints) w
    WHERE w.at = 'any';
    SELECT v_points || array_agg(t.geom ORDER BY o.n),
           v_kinds || array_agg(t.kind ORDER BY o.n),
           v_after_m || array_agg(t.after_m ORDER BY o.n),
           v_ns || array_agg(t.n ORDER BY o.n)
    INTO v_points, v_kinds, v_after_m, v_ns
    FROM unnest(routing.insertion_order(v_tail, v_any)) WITH ORDINALITY AS o(i, n)
    JOIN LATERAL (
        SELECT (v_tail || v_any)[o.i] AS geom,
               (v_tail_kind || array_fill('any'::text, ARRAY[cardinality(v_any)]))[o.i] AS kind,
               v_tail_m[o.i] AS after_m,
               (v_tail_n || v_any_n)[o.i] AS n
    ) t ON true
    WHERE o.n > 1;

    RETURN QUERY
        SELECT u.k::integer, u.geom, v_kinds[u.k], v_after_m[u.k], v_ns[u.k]
        FROM unnest(v_points) WITH ORDINALITY AS u(geom, k);
END
$$;

-- p_a followed by p_b, as much of routing.route_json as carrying a route on needs: the line,
-- the length and the edges with their directions. p_a may be NULL, for nothing before.
CREATE FUNCTION routing.joined(p_a jsonb, p_b jsonb) RETURNS jsonb
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE WHEN p_a IS NULL THEN p_b ELSE jsonb_build_object(
        'geometry', ST_AsGeoJSON(ST_MakeLine(
            ST_GeomFromGeoJSON(p_a -> 'geometry'), ST_GeomFromGeoJSON(p_b -> 'geometry')
        ))::jsonb,
        'length_m', (p_a ->> 'length_m')::double precision + (p_b ->> 'length_m')::double precision,
        'edges', (p_a -> 'edges') || (p_b -> 'edges'),
        'forward', (p_a -> 'forward') || (p_b -> 'forward')
    ) END
$$;

-- routing.score for p_route (from routing.route_json) after p_before (NULL: nothing before),
-- measured as routing.evaluate measures a candidate.
CREATE FUNCTION routing.route_score(
    p_profile routing.profile, p_target_m double precision, p_route jsonb, p_before jsonb
) RETURNS double precision
LANGUAGE sql STABLE AS $$
    WITH lines AS (
        SELECT ST_GeomFromGeoJSON(p_route -> 'geometry') AS route,
               ST_GeomFromGeoJSON(p_before -> 'geometry') AS before
    )
    SELECT routing.score(
        p_target_m,
        (p_route ->> 'length_m')::double precision,
        routing.preference(p_profile.weights, p_route -> 'scores'),
        CASE WHEN lines.before IS NULL
            THEN routing.doubled_m(lines.route, p_profile.settings -> 'doubling')
            ELSE greatest(
                routing.doubled_m(
                    ST_MakeLine(lines.before, lines.route), p_profile.settings -> 'doubling'
                ) - routing.doubled_m(lines.before, p_profile.settings -> 'doubling'),
                0
            )
        END,
        (p_route ->> 'reused_m')::double precision + coalesce((
            SELECT sum(e.length_m)
            FROM graph.edges e
            WHERE e.id IN (SELECT r::bigint FROM jsonb_array_elements_text(p_route -> 'edges') r)
              AND e.id IN (SELECT b::bigint FROM jsonb_array_elements_text(p_before -> 'edges') b)
        ), 0),
        p_profile.settings -> 'score'
    )
    FROM lines
$$;

-- The share of the shorter of two routes (as routing.route_json gives them) that is on edges
-- both use, each edge counted once.
CREATE FUNCTION routing.overlap(p_a jsonb, p_b jsonb) RETURNS double precision
LANGUAGE sql STABLE AS $$
    SELECT coalesce(sum(e.length_m), 0) / nullif(least(
        (p_a ->> 'length_m')::double precision, (p_b ->> 'length_m')::double precision
    ), 0)
    FROM graph.edges e
    WHERE e.id IN (SELECT a::bigint FROM jsonb_array_elements_text(p_a -> 'edges') a)
      AND e.id IN (SELECT b::bigint FROM jsonb_array_elements_text(p_b -> 'edges') b)
$$;

-- One piece of a route: from p_from to p_to (the same vertex for a loop), after p_before, the
-- route so far (NULL: nothing before). Without p_target_m it is the cheapest way there. With it,
-- the piece that comes nearest p_target_m and scores best, going back over p_before and
-- alongside it counting against it.
-- As routing.route_json gives it, with vias (the vertices it passes) and direct (whether it
-- takes the way that is not shaped to a target). The plan settings are read here.
-- Candidates are generated and scored in bulk; if the best misses the tolerance, the goal is
-- scaled by how much it missed and candidates are tried again, up to attempts (2) times, keeping
-- the best kept (3) of each. Evaluation leaves out the reuse penalty, so a route can come out
-- otherwise than evaluated; when it misses the tolerance, the next best candidates are routed
-- too, up to routed (3) in all, and the one whose route scores best is returned.
-- With p_options above 1 and a target, up to p_options - 1 other routes come with it as options,
-- best first: the next ranked candidates are routed too, up to options.routed in all, and an
-- option is kept if it scores at most options.margin worse than the best, misses the target by
-- no more than the tolerance or the best does, and shares no more than options.overlap of the
-- shorter route with the best or another option. No more candidates are routed after p_until.
-- Without a target, options are the cheapest way there again with the edges of the best and of
-- those found before penalised (see routing.route_edges), up to options.routed tries, kept on the
-- same terms but for their length, which may be up to options.longer more than the best's.
-- Raises no_data_found with DETAIL no_loop or unreachable when there is no candidate.
CREATE FUNCTION routing.segment_route(
    p_profile   routing.profile,
    p_area      geometry,
    p_from      bigint,
    p_to        bigint,
    p_target_m  double precision,
    p_before    jsonb DEFAULT NULL,
    p_options   integer DEFAULT 1,
    p_until     timestamptz DEFAULT NULL
) RETURNS jsonb
LANGUAGE plpgsql AS $$
DECLARE
    v_tolerance  double precision := routing.setting(p_profile, 'plan', 'tolerance');
    v_direct     bigint[] := ARRAY[p_from, p_to];
    v_goal_m     double precision := p_target_m;
    -- All NULL until a candidate is found.
    v_best       routing.evaluation;
    v_retry      routing.evaluation;
    -- The best few of every attempt, to route when the best one comes out wrong.
    v_ranked     routing.evaluation[] := '{}';
    v_try        routing.evaluation;
    v_routed     jsonb;
    v_score      double precision;
    v_route      jsonb;
    v_vias       bigint[];
    v_best_score double precision;
    v_kept       integer := routing.setting(p_profile, 'plan', 'kept')::integer;
    -- Every route found so far, with its vias and score, so an option is not routed twice.
    v_tried      jsonb := '[]';
    v_option     jsonb;
    v_options    jsonb := '[]';
    v_avoid      bigint[];
BEGIN
    IF p_target_m IS NULL THEN
        v_route := routing.route_json(p_profile, p_area, v_direct, '{}');
        -- Options go other ways: each is routed again with every edge taken so far penalised.
        -- Its length is held to options.longer, so it is scored as if it were the length wanted.
        v_best_score := routing.route_score(
            p_profile, (v_route ->> 'length_m')::double precision, v_route, p_before
        );
        v_avoid := ARRAY(SELECT e::bigint FROM jsonb_array_elements_text(v_route -> 'edges') e);
        FOR k IN 1 .. CASE WHEN p_options > 1
            THEN routing.setting(p_profile, 'options', 'routed')::integer
            ELSE 0
        END LOOP
            EXIT WHEN jsonb_array_length(v_options) >= p_options - 1
                OR clock_timestamp() > p_until;
            v_option := routing.route_json(p_profile, p_area, v_direct, '{}', v_avoid);
            v_avoid := v_avoid
                || ARRAY(SELECT e::bigint FROM jsonb_array_elements_text(v_option -> 'edges') e);
            CONTINUE WHEN (v_option ->> 'length_m')::double precision
                > (1 + routing.setting(p_profile, 'options', 'longer'))
                    * (v_route ->> 'length_m')::double precision;
            CONTINUE WHEN routing.route_score(
                    p_profile, (v_option ->> 'length_m')::double precision, v_option, p_before
                ) > v_best_score + routing.setting(p_profile, 'options', 'margin');
            CONTINUE WHEN EXISTS (
                SELECT FROM jsonb_array_elements(v_options || jsonb_build_array(v_route)) o
                WHERE routing.overlap(o, v_option)
                    > routing.setting(p_profile, 'options', 'overlap')
            );
            v_options := v_options || jsonb_build_array(
                v_option || jsonb_build_object('vias', v_direct, 'direct', true)
            );
        END LOOP;
        RETURN v_route
            || jsonb_build_object('vias', v_direct, 'direct', true, 'options', v_options);
    END IF;
    IF p_options > 1 THEN
        v_kept := greatest(v_kept, routing.setting(p_profile, 'options', 'routed')::integer);
    END IF;

    FOR attempt IN 1 .. routing.setting(p_profile, 'plan', 'attempts')::integer LOOP
        v_ranked := v_ranked || ARRAY(
            SELECT e
            FROM routing.evaluate(
                p_profile,
                p_area,
                p_target_m,
                ARRAY(
                    SELECT c FROM routing.loop_candidates(p_profile, p_area, p_from, v_goal_m) c
                    WHERE p_from = p_to
                    UNION ALL
                    SELECT c
                    FROM routing.detour_candidates(p_profile, p_area, p_from, p_to, v_goal_m) c
                    WHERE p_from <> p_to
                ),
                p_before
            ) e
            ORDER BY e.score
            LIMIT v_kept
        );
        SELECT * INTO v_retry FROM unnest(v_ranked) e ORDER BY e.score LIMIT 1;
        IF FOUND AND (v_best.vias IS NULL OR v_retry.score < v_best.score) THEN
            v_best := v_retry;
        END IF;
        EXIT WHEN v_best.vias IS NULL
            OR abs(v_best.length_m - p_target_m) <= v_tolerance * p_target_m
            -- Only the direct route is left; a longer goal finds nothing shorter.
            OR (v_best.vias = v_direct AND v_best.length_m > p_target_m);
        v_goal_m := v_goal_m * p_target_m / v_best.length_m;
    END LOOP;

    IF v_best.vias IS NULL THEN
        IF p_from = p_to THEN
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
        LIMIT routing.setting(p_profile, 'plan', 'routed')::integer
    LOOP
        v_routed := routing.route_json(p_profile, p_area, v_try.vias, '{}');
        v_score := routing.route_score(p_profile, p_target_m, v_routed, p_before);
        v_tried := v_tried || jsonb_build_array(
            v_routed || jsonb_build_object('vias', v_try.vias, 'score', v_score)
        );
        IF v_route IS NULL OR v_score < v_best_score THEN
            v_route := v_routed;
            v_vias := v_try.vias;
            v_best_score := v_score;
        END IF;
        EXIT WHEN abs((v_route ->> 'length_m')::double precision - p_target_m)
            <= v_tolerance * p_target_m;
    END LOOP;

    IF p_options > 1 THEN
        FOR v_try IN
            SELECT d.* FROM (
                SELECT DISTINCT ON (e.vias) e.* FROM unnest(v_ranked) e ORDER BY e.vias, e.score
            ) d
            WHERE d.vias <> v_vias
            ORDER BY d.score
            LIMIT routing.setting(p_profile, 'options', 'routed')::integer
        LOOP
            EXIT WHEN jsonb_array_length(v_options) >= p_options - 1;
            SELECT t INTO v_option FROM jsonb_array_elements(v_tried) t
            WHERE t -> 'vias' = to_jsonb(v_try.vias);
            IF v_option IS NULL THEN
                EXIT WHEN clock_timestamp() > p_until;
                v_routed := routing.route_json(p_profile, p_area, v_try.vias, '{}');
                v_option := v_routed || jsonb_build_object(
                    'vias', v_try.vias,
                    'score', routing.route_score(p_profile, p_target_m, v_routed, p_before)
                );
            END IF;
            CONTINUE WHEN (v_option ->> 'score')::double precision
                > v_best_score + routing.setting(p_profile, 'options', 'margin');
            CONTINUE WHEN abs((v_option ->> 'length_m')::double precision - p_target_m)
                > greatest(
                    v_tolerance * p_target_m,
                    abs((v_route ->> 'length_m')::double precision - p_target_m)
                );
            CONTINUE WHEN EXISTS (
                SELECT FROM jsonb_array_elements(v_options || jsonb_build_array(v_route)) k
                WHERE routing.overlap(k, v_option)
                    > routing.setting(p_profile, 'options', 'overlap')
            );
            v_options := v_options || jsonb_build_array(
                v_option || jsonb_build_object('direct', v_try.vias = v_direct)
            );
        END LOOP;
        v_options := coalesce((
            SELECT jsonb_agg(o - 'score' ORDER BY (o ->> 'score')::double precision)
            FROM jsonb_array_elements(v_options) o
        ), '[]');
    END IF;
    RETURN v_route || jsonb_build_object(
        'vias', v_vias, 'direct', v_vias = v_direct, 'options', v_options
    );
END
$$;

-- The warnings for a route of p_length_m planned to p_target_m (NULL: none): too_short when it
-- misses the target by more than p_tolerance (a share of it) and is longer, while it takes the
-- direct way (p_direct), so nothing shorter exists; target_missed when it misses it otherwise.
CREATE FUNCTION routing.length_warnings(
    p_length_m double precision,
    p_target_m double precision,
    p_tolerance double precision,
    p_direct boolean
) RETURNS jsonb
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE
        WHEN abs(p_length_m - p_target_m) > p_tolerance * p_target_m THEN to_jsonb(ARRAY[CASE
            WHEN p_direct AND p_length_m > p_target_m THEN 'too_short'
            ELSE 'target_missed'
        END])
        ELSE '[]'::jsonb
    END
$$;

-- A route from routing.route_json as the API returns it: the line, length, reused length and
-- warnings, the edges in travel order as {edge_id, forward}, and the scores as
-- routing.route_scores gives them.
CREATE FUNCTION routing.route_out(p_route jsonb) RETURNS jsonb
LANGUAGE sql STABLE AS $$
    WITH steps AS (
        SELECT e.id::bigint AS edge_id, f.forward::boolean AS forward, e.n
        FROM jsonb_array_elements_text(p_route -> 'edges') WITH ORDINALITY AS e (id, n)
        JOIN jsonb_array_elements_text(p_route -> 'forward') WITH ORDINALITY AS f (forward, n)
            ON f.n = e.n
    )
    SELECT jsonb_build_object(
        'geometry', p_route -> 'geometry',
        'length_m', p_route -> 'length_m',
        'reused_m', p_route -> 'reused_m',
        'warnings', p_route -> 'warnings',
        'edges', (
            SELECT jsonb_agg(jsonb_build_object('edge_id', edge_id, 'forward', forward) ORDER BY n)
            FROM steps
        ),
        'scores', routing.route_scores(ARRAY(SELECT edge_id FROM steps ORDER BY n))
    )
$$;

-- The vias of a plan from routing.plan_rest, or of its varied piece, as an array.
CREATE FUNCTION routing.vias(p_plan jsonb) RETURNS bigint[]
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT ARRAY(
        SELECT u.v::bigint
        FROM jsonb_array_elements_text(p_plan -> 'vias') WITH ORDINALITY AS u(v, n)
        ORDER BY u.n
    )
$$;

-- The pieces of a route after point p_from of p_points (in travel order, with p_kinds, p_after_m
-- and the vertices they snapped to, as routing.plan_route has them), carrying on p_before (the
-- route so far, NULL for none), p_vias (its vias) and p_direct (whether every piece shaped to a
-- target so far took the direct way). A piece to an after waypoint is shaped to the length still
-- to go before it, one to the end to what is left of p_target_m, and one to an any waypoint to its
-- share of the length still to go to the next of those, by straight distance; a piece to where
-- the last one ended is left out, but for a loop with nothing else.
-- With p_options above 1, the first piece shaped to a target (the first piece, when p_target_m is
-- NULL) is asked for options; that piece and the plan before it come back as varied: at (the
-- point it ends at), before, vias and direct (as they were before it), targeted, and options.
-- Returns vias, direct, pieces (how many were planned), piece (the last one) and varied.
CREATE FUNCTION routing.plan_rest(
    p_profile  routing.profile,
    p_area     geometry,
    p_points   geometry[],
    p_kinds    text[],
    p_after_m  double precision[],
    p_vertices bigint[],
    p_target_m double precision,
    p_from     integer,
    p_before   jsonb,
    p_vias     bigint[],
    p_direct   boolean,
    p_options  integer,
    p_until    timestamptz
) RETURNS jsonb
LANGUAGE plpgsql AS $$
DECLARE
    v_from     integer := p_from;
    v_before   jsonb := p_before;
    v_vias     bigint[] := p_vias;
    v_direct   boolean := p_direct;
    v_next     integer;
    v_target_m double precision;
    v_asked    integer;
    v_piece    jsonb;
    v_pieces   integer := 0;
    v_varied   jsonb;
BEGIN
    FOR i IN p_from + 1 .. cardinality(p_points) LOOP
        -- The next point whose place on the route is known: an asap waypoint (as soon as
        -- possible), an after waypoint or the end.
        SELECT min(k) INTO v_next
        FROM generate_series(i, cardinality(p_points)) k
        WHERE p_kinds[k] <> 'any';
        v_target_m := CASE p_kinds[v_next]
                WHEN 'asap' THEN NULL
                WHEN 'after' THEN p_after_m[v_next]
                ELSE p_target_m
            END - coalesce((v_before ->> 'length_m')::double precision, 0);
        -- An any waypoint's piece gets its share of the way to the next point.
        IF i < v_next THEN
            v_target_m := v_target_m
                * ST_Distance(p_points[v_from]::geography, p_points[i]::geography)
                / nullif((
                    SELECT sum(ST_Distance(p_points[k - 1]::geography, p_points[k]::geography))
                    FROM generate_series(v_from + 1, v_next) k
                ), 0);
        END IF;
        -- Already past where the piece should end: the direct way is all there is.
        IF v_target_m <= 0 THEN
            v_target_m := NULL;
        END IF;
        IF p_vertices[v_from] <> p_vertices[i] OR (p_kinds[i] = 'end' AND v_before IS NULL) THEN
            v_asked := CASE
                WHEN v_varied IS NULL AND (v_target_m IS NOT NULL OR p_target_m IS NULL)
                THEN p_options
                ELSE 1
            END;
            v_piece := routing.segment_route(
                p_profile, p_area, p_vertices[v_from], p_vertices[i], v_target_m, v_before,
                v_asked, p_until
            );
            IF v_asked > 1 THEN
                v_varied := jsonb_build_object(
                    'at', i, 'before', v_before, 'vias', v_vias, 'direct', v_direct,
                    'targeted', v_target_m IS NOT NULL, 'options', v_piece -> 'options'
                );
            END IF;
            v_pieces := v_pieces + 1;
            -- The piece starts where the last one ended.
            v_vias := v_vias || ARRAY(
                SELECT u.v::bigint
                FROM jsonb_array_elements_text(v_piece -> 'vias') WITH ORDINALITY AS u(v, n)
                WHERE u.n > 1
                ORDER BY u.n
            );
            -- Only pieces shaped to a target say whether the route could be shorter.
            IF v_target_m IS NOT NULL THEN
                v_direct := v_direct AND (v_piece ->> 'direct')::boolean;
            END IF;
            v_before := routing.joined(v_before, v_piece);
            v_from := i;
        END IF;
    END LOOP;
    RETURN jsonb_build_object(
        'vias', v_vias, 'direct', v_direct, 'pieces', v_pieces, 'piece', v_piece,
        'varied', v_varied
    );
END
$$;

-- Plans a route for p_activity from p_start to p_finish, or back to p_start when p_finish is
-- NULL, weighting edge scores by p_weights; p_settings overrides routing.defaults() (see
-- routing.make_profile). With p_target_m, the route is about that long; without it, which only a
-- route to a finish may leave out, it is the cheapest way there by the cost every route is found
-- by (see routing.cost_sql): the most pleasant one, without a length to keep to.
-- p_waypoints (see routing.read_waypoints) are passed on the way: those at asap first, in the
-- order given, each by the cheapest way from the last; then those at after, by after_m, and
-- those at any where they lengthen the way least by straight distance. The route is planned in
-- pieces from one point to the next (see routing.segment_route), each scored after the pieces
-- before it, so that it does not come back along them: a piece to an after waypoint is shaped
-- to the length still to go before it, one to the end to what is left of the target, and one
-- to an any waypoint to its share of the length still to go to the next of those, by straight
-- distance. A piece to where the last one ended is left out, but for a loop with nothing else
-- (see routing.plan_rest). The whole route is then routed through all their vias in one go, and
-- returned as routing.route_out gives it, with waypoint_order: the waypoints' indexes in
-- p_waypoints (from 0) in the order the route passes them; and options, other routes in the same
-- form, best first. Options differ from the first piece shaped to a target on (the first piece,
-- without a target), which offers them as routing.segment_route does; the pieces after it are
-- planned anew behind each. Put together, none misses the target by more than the tolerance or
-- the route does, or shares more than options.overlap with the route or another option.
-- The points are snapped to roads that join (see routing.snap_points), so a path cut off from
-- the rest is not taken for the way there.
-- Warnings, judged on the route: too_short (the direct way through the points is longer than
-- the target), target_missed (it misses the target by more than plan.tolerance).
-- Raises invalid_parameter_value for bad input, and no_data_found when there is no route; its
-- detail says why, for the API to pass on: start_off_road, waypoint_off_road or finish_off_road
-- (no road within snap_m), unreachable (no way from the start to the finish, or both at the same
-- place without a target) or no_loop (too few roads around the start to come back by another
-- way).
-- JIT is off: the planner's queries are mostly calls to functions it cannot compile, and their
-- cost estimates, made without knowing how many rows those return, would often pass the JIT
-- threshold and spend more time compiling than the query takes.
CREATE FUNCTION routing.plan_route(
    p_activity  text,
    p_start     geometry,
    p_finish    geometry,
    p_target_m  double precision,
    p_weights   jsonb DEFAULT '{}',
    p_settings  jsonb DEFAULT '{}',
    p_waypoints jsonb DEFAULT '[]'
) RETURNS jsonb
LANGUAGE plpgsql
SET jit = off
AS $$
DECLARE
    v_profile   routing.profile;
    v_end       geometry := coalesce(p_finish, p_start);
    -- The points in travel order from the start to the end, what each is, and after_m.
    v_points    geometry[];
    v_kinds     text[];
    v_after_m   double precision[];
    -- Which waypoint each point is (its place in p_waypoints, from 1); NULL for the start and end.
    v_ns        integer[];
    v_area      geometry;
    v_vertices  bigint[];
    v_plan      jsonb;
    v_route     jsonb;
    v_tolerance double precision;
    v_count     integer;
    v_until     timestamptz;
    v_varied    jsonb;
    v_rest      jsonb;
    v_option    jsonb;
    v_options   jsonb := '[]';
    v_order     jsonb;
BEGIN
    IF p_start IS NULL OR p_target_m <= 0 OR (p_target_m IS NULL AND p_finish IS NULL) THEN
        RAISE EXCEPTION 'need a start, and a positive target or a finish'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;
    v_profile := routing.make_profile(p_activity, p_weights, p_settings);
    v_tolerance := routing.setting(v_profile, 'plan', 'tolerance');
    v_count := routing.setting(v_profile, 'options', 'count')::integer;
    v_until := clock_timestamp()
        + make_interval(secs => routing.setting(v_profile, 'options', 'budget_ms') / 1000);

    SELECT array_agg(t.geom ORDER BY t.k), array_agg(t.kind ORDER BY t.k),
           array_agg(t.after_m ORDER BY t.k), array_agg(t.n ORDER BY t.k)
    INTO v_points, v_kinds, v_after_m, v_ns
    FROM routing.travel_points(p_start, v_end, p_waypoints) t;

    v_area := routing.search_area(
        p_start, p_finish, p_target_m, v_profile.settings -> 'area',
        v_points[2:cardinality(v_points) - 1]
    );
    -- A loop's end is its start, which is snapped once.
    v_vertices := routing.snap_points(
        v_profile,
        v_area,
        CASE WHEN p_finish IS NULL THEN v_points[1:cardinality(v_points) - 1] ELSE v_points END,
        ARRAY(
            SELECT CASE k WHEN 'start' THEN 'start' WHEN 'end' THEN 'finish' ELSE 'waypoint' END
            FROM unnest(v_kinds) k
        ),
        CASE WHEN p_finish IS NULL
            THEN routing.setting(v_profile, 'plan', 'loop_network') * p_target_m
            ELSE 0
        END
    );
    IF v_vertices IS NOT NULL AND p_finish IS NULL THEN
        v_vertices := v_vertices || v_vertices[1];
    END IF;
    IF v_vertices IS NULL
        OR (p_target_m IS NULL AND (SELECT count(DISTINCT v) FROM unnest(v_vertices) v) = 1)
    THEN
        RAISE EXCEPTION '%', CASE WHEN p_finish IS NULL
                THEN 'too few roads around the start for a loop'
                ELSE 'the finish cannot be reached from the start'
            END
            USING ERRCODE = 'no_data_found',
                  DETAIL = CASE WHEN p_finish IS NULL THEN 'no_loop' ELSE 'unreachable' END;
    END IF;

    v_plan := routing.plan_rest(
        v_profile, v_area, v_points, v_kinds, v_after_m, v_vertices, p_target_m,
        1, NULL, ARRAY[v_vertices[1]], true, v_count, v_until
    );
    v_route := CASE WHEN (v_plan ->> 'pieces')::integer = 1
        THEN (v_plan -> 'piece') - 'vias' - 'direct' - 'options'
        ELSE routing.route_json(v_profile, v_area, routing.vias(v_plan), '{}')
    END;
    v_route := jsonb_set(v_route, '{warnings}', routing.length_warnings(
        (v_route ->> 'length_m')::double precision, p_target_m, v_tolerance,
        (v_plan ->> 'direct')::boolean
    ));

    -- Each option takes the varied piece's place, and the pieces after it are planned anew.
    v_varied := v_plan -> 'varied';
    FOR v_option IN SELECT o FROM jsonb_array_elements(v_varied -> 'options') o LOOP
        EXIT WHEN clock_timestamp() > v_until;
        IF (v_plan ->> 'pieces')::integer = 1 THEN
            v_option := v_option - 'vias' || jsonb_build_object(
                'direct', (v_option ->> 'direct')::boolean OR NOT (v_varied ->> 'targeted')::boolean
            );
        ELSE
            v_rest := routing.plan_rest(
                v_profile, v_area, v_points, v_kinds, v_after_m, v_vertices, p_target_m,
                (v_varied ->> 'at')::integer,
                routing.joined(nullif(v_varied -> 'before', 'null'), v_option),
                routing.vias(v_varied) || ARRAY(
                    SELECT u.v::bigint
                    FROM jsonb_array_elements_text(v_option -> 'vias') WITH ORDINALITY AS u(v, n)
                    WHERE u.n > 1
                    ORDER BY u.n
                ),
                (v_varied ->> 'direct')::boolean AND (
                    (v_option ->> 'direct')::boolean OR NOT (v_varied ->> 'targeted')::boolean
                ),
                1, v_until
            );
            v_option := routing.route_json(v_profile, v_area, routing.vias(v_rest), '{}')
                || jsonb_build_object('direct', v_rest -> 'direct');
        END IF;
        v_option := jsonb_set(v_option - 'direct', '{warnings}', routing.length_warnings(
            (v_option ->> 'length_m')::double precision, p_target_m, v_tolerance,
            (v_option ->> 'direct')::boolean
        ));
        -- Put together, an option may come out longer or shorter than its piece did, or run
        -- along the route after it.
        CONTINUE WHEN abs((v_option ->> 'length_m')::double precision - p_target_m) > greatest(
            v_tolerance * p_target_m,
            abs((v_route ->> 'length_m')::double precision - p_target_m)
        );
        CONTINUE WHEN EXISTS (
            SELECT FROM jsonb_array_elements(v_options || jsonb_build_array(v_route)) k
            WHERE routing.overlap(k, v_option) > routing.setting(v_profile, 'options', 'overlap')
        );
        v_options := v_options || jsonb_build_array(v_option);
    END LOOP;

    v_order := to_jsonb(ARRAY(
        SELECT u.n - 1 FROM unnest(v_ns) WITH ORDINALITY AS u(n, k)
        WHERE u.n IS NOT NULL
        ORDER BY u.k
    ));
    RETURN routing.route_out(v_route) || jsonb_build_object(
        'waypoint_order', v_order,
        'options', coalesce((
            SELECT jsonb_agg(
                routing.route_out(o) || jsonb_build_object('waypoint_order', v_order)
                ORDER BY n
            )
            FROM jsonb_array_elements(v_options) WITH ORDINALITY AS u(o, n)
        ), '[]')
    );
END
$$;

-- A route along p_edge_ids, travelled from source to target where p_forward says so, in the form
-- routing.route_json gives (without scores): its line, length, the length travelled more than
-- once, the edges and their directions, and no warnings.
CREATE FUNCTION routing.steps_json(p_edge_ids bigint[], p_forward boolean[]) RETURNS jsonb
LANGUAGE sql STABLE AS $$
    WITH path AS MATERIALIZED (
        SELECT s.n, e.id, e.length_m, s.forward,
               CASE WHEN s.forward THEN e.geom ELSE ST_Reverse(e.geom) END AS geom
        FROM unnest(p_edge_ids, p_forward) WITH ORDINALITY AS s (id, forward, n)
        JOIN graph.edges e ON e.id = s.id
    ),
    total AS (
        SELECT sum(length_m ORDER BY n) AS length_m FROM path
    ),
    reused AS (
        SELECT coalesce(sum(length_m * (times - 1)), 0) AS length_m
        FROM (SELECT min(length_m) AS length_m, count(*) AS times FROM path GROUP BY id) u
    )
    SELECT jsonb_build_object(
        'geometry', (SELECT ST_AsGeoJSON(ST_MakeLine(geom ORDER BY n))::jsonb FROM path),
        'length_m', total.length_m,
        'reused_m', reused.length_m,
        'edges', (SELECT to_jsonb(array_agg(id ORDER BY n)) FROM path),
        'forward', (SELECT to_jsonb(array_agg(forward ORDER BY n)) FROM path),
        'warnings', '[]'::jsonb
    )
    FROM total, reused
$$;

-- p_activity's route along p_edge_ids (in travel order, from source to target where p_forward
-- says so) changed where it was grabbed at p_grab, so that it passes p_drop: the stretch from the
-- junction at or before edit.window_min_m, or window_share times the drag, before the grab to the
-- one as far after it is routed again through the edge p_activity may use nearest p_drop (within
-- plan.snap_m), in whichever direction is shorter. Everything outside the stretch stays as it
-- was. The new way is the cheapest by the activity's own cost, highway class and turns, without
-- preferences, so an edit goes the way it was dragged; edges outside the stretch pay the reuse
-- penalty. Without p_drop, the stretch is routed again with nothing to pass, which takes an edit
-- back out. p_settings overrides routing.defaults() as in routing.make_profile.
-- Returns the route as routing.route_out gives it, warned against p_target_m (NULL: no target) as
-- a planned one is, with handle: where p_drop came onto the road, a GeoJSON point (NULL without
-- p_drop).
-- Raises invalid_parameter_value for edges that are not in the graph, do not join up or may not
-- be used that way, and no_data_found with DETAIL drop_off_road (no road near p_drop) or
-- unreachable.
CREATE FUNCTION routing.reroute(
    p_activity text,
    p_edge_ids bigint[],
    p_forward  boolean[],
    p_grab     geometry,
    p_drop     geometry,
    p_target_m double precision DEFAULT NULL,
    p_settings jsonb DEFAULT '{}'
) RETURNS jsonb
LANGUAGE plpgsql
SET jit = off
AS $$
DECLARE
    v_profile  routing.profile := routing.make_profile(p_activity, '{}', p_settings);
    v_n        integer := cardinality(p_edge_ids);
    -- Per edge in travel order: the vertex it is entered from and left at, and where it ends
    -- along the route.
    v_enter    bigint[];
    v_leave    bigint[];
    v_end_m    double precision[];
    v_line     geometry;
    v_grab_m   double precision;
    v_reach_m  double precision;
    -- The stretch is edges v_first + 1 .. v_last - 1.
    v_first    integer;
    v_last     integer;
    v_area     geometry;
    v_edge     record;
    v_handle   geometry;
    v_tries    bigint[][];
    v_stretch  bigint[];
    v_forward  boolean[];
    v_best_ids bigint[];
    v_best_fw  boolean[];
    v_best_m   double precision;
    v_m        double precision;
    v_route    jsonb;
BEGIN
    SELECT array_agg(t.enter ORDER BY t.n), array_agg(t.leave ORDER BY t.n),
           array_agg(t.end_m ORDER BY t.n)
    INTO v_enter, v_leave, v_end_m
    FROM (
        SELECT s.n,
               CASE WHEN s.forward THEN e.source ELSE e.target END AS enter,
               CASE WHEN s.forward THEN e.target ELSE e.source END AS leave,
               sum(e.length_m) OVER (ORDER BY s.n) AS end_m
        FROM unnest(p_edge_ids, p_forward) WITH ORDINALITY AS s (id, forward, n)
        JOIN graph.edges e ON e.id = s.id
        WHERE p_activity = ANY (CASE WHEN s.forward THEN e.forward ELSE e.backward END)
    ) t;
    IF v_n = 0 OR cardinality(p_forward) <> v_n OR coalesce(cardinality(v_enter), 0) <> v_n
        OR EXISTS (SELECT FROM generate_series(1, v_n - 1) i WHERE v_leave[i] <> v_enter[i + 1])
    THEN
        RAISE EXCEPTION 'the edges must be in the graph, join up and allow %', p_activity
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    -- In Web Mercator, where shares of the line's length are true to those in metres.
    v_line := ST_Transform(
        ST_GeomFromGeoJSON(routing.steps_json(p_edge_ids, p_forward) -> 'geometry'), 3857
    );
    v_grab_m := ST_LineLocatePoint(v_line, ST_Transform(p_grab, 3857)) * v_end_m[v_n];
    v_reach_m := greatest(
        routing.setting(v_profile, 'edit', 'window_min_m'),
        routing.setting(v_profile, 'edit', 'window_share')
            * coalesce(ST_Distance(p_grab::geography, p_drop::geography), 0)
    );
    SELECT coalesce(max(i), 0) INTO v_first
    FROM generate_series(1, v_n) i
    WHERE v_end_m[i] <= v_grab_m - v_reach_m;
    SELECT coalesce(min(i), v_n + 1) INTO v_last
    FROM generate_series(1, v_n) i
    WHERE coalesce(v_end_m[i - 1], 0) >= v_grab_m + v_reach_m;

    v_area := ST_Buffer(
        ST_Collect(ARRAY[
            ST_Transform(ST_LineSubstring(
                v_line,
                coalesce(v_end_m[v_first], 0) / v_end_m[v_n],
                coalesce(v_end_m[v_last - 1], v_end_m[v_n]) / v_end_m[v_n]
            ), 4326),
            coalesce(p_drop, p_grab)
        ])::geography,
        routing.setting(v_profile, 'edit', 'area_m')
    )::geometry;

    IF p_drop IS NULL THEN
        v_tries := ARRAY[ARRAY[
            coalesce(v_leave[v_first], v_enter[1]), coalesce(v_enter[v_last], v_leave[v_n])
        ]];
    ELSE
        SELECT a.source, a.target, a.forward, a.backward, a.geom INTO v_edge
        FROM routing.activity_edges a
        WHERE a.activity = p_activity
          AND a.geom && ST_Buffer(
              p_drop::geography, routing.setting(v_profile, 'plan', 'snap_m')
          )::geometry
          AND ST_DWithin(
              a.geom::geography, p_drop::geography, routing.setting(v_profile, 'plan', 'snap_m')
          )
        ORDER BY ST_Distance(a.geom::geography, p_drop::geography)
        LIMIT 1;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'no road near where the route was dropped'
                USING ERRCODE = 'no_data_found', DETAIL = 'drop_off_road';
        END IF;
        v_handle := ST_ClosestPoint(v_edge.geom, p_drop);
        v_tries := '{}';
        IF v_edge.forward THEN
            v_tries := v_tries || ARRAY[ARRAY[
                coalesce(v_leave[v_first], v_enter[1]), v_edge.source, v_edge.target,
                coalesce(v_enter[v_last], v_leave[v_n])
            ]];
        END IF;
        IF v_edge.backward THEN
            v_tries := v_tries || ARRAY[ARRAY[
                coalesce(v_leave[v_first], v_enter[1]), v_edge.target, v_edge.source,
                coalesce(v_enter[v_last], v_leave[v_n])
            ]];
        END IF;
    END IF;

    FOR i IN 1 .. array_length(v_tries, 1) LOOP
        BEGIN
            SELECT array_agg(r.edge_id ORDER BY r.step),
                   array_agg(r.vertex = e.source ORDER BY r.step),
                   coalesce(sum(e.length_m), 0)
            INTO v_stretch, v_forward, v_m
            FROM routing.route_edges(
                v_profile,
                v_area,
                ARRAY(SELECT unnest(v_tries[i:i][:])),
                p_edge_ids[1:v_first] || p_edge_ids[v_last:]
            ) r
            JOIN graph.edges e ON e.id = r.edge_id;
        EXCEPTION WHEN no_data_found THEN
            CONTINUE;
        END;
        IF v_best_m IS NULL OR v_m < v_best_m THEN
            v_best_ids := coalesce(v_stretch, '{}');
            v_best_fw := coalesce(v_forward, '{}');
            v_best_m := v_m;
        END IF;
    END LOOP;
    IF v_best_m IS NULL THEN
        RAISE EXCEPTION 'no way through where the route was dropped'
            USING ERRCODE = 'no_data_found', DETAIL = 'unreachable';
    END IF;

    v_route := routing.steps_json(
        p_edge_ids[1:v_first] || v_best_ids || p_edge_ids[v_last:],
        p_forward[1:v_first] || v_best_fw || p_forward[v_last:]
    );
    v_route := jsonb_set(v_route, '{warnings}', routing.length_warnings(
        (v_route ->> 'length_m')::double precision, p_target_m,
        routing.setting(v_profile, 'plan', 'tolerance'), false
    ));
    RETURN routing.route_out(v_route)
        || jsonb_build_object('handle', ST_AsGeoJSON(v_handle)::jsonb);
END
$$;
