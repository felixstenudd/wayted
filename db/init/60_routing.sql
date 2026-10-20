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
    reuse_penalty double precision
);

-- Weights run from -1 (avoid) to 1 (prefer) per edge score key, e.g. {"green": 1}. They are
-- scaled so an edge's preference stays in [-1, 1] however many keys are weighted, which keeps
-- cost between (1 - alpha) and (1 + alpha) times length * factor, and so always positive.
-- Raises invalid_parameter_value for an unknown activity or a value out of range.
CREATE FUNCTION routing.make_profile(
    p_activity      text,
    p_weights       jsonb            DEFAULT '{}',
    p_alpha         double precision DEFAULT 0.7,
    p_reuse_penalty double precision DEFAULT 4
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
        RAISE EXCEPTION 'reuse_penalty must be at least 1' USING ERRCODE = 'invalid_parameter_value';
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
        p_reuse_penalty
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
