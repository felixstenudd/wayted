"""SQL for one mapper batch, in the order mapper.py runs it. Work tables are dropped at commit."""

CREATE_WORK_TABLES = """
    CREATE TEMP TABLE claimed_ways (id bigint PRIMARY KEY) ON COMMIT DROP;
    CREATE TEMP TABLE moved_nodes (id bigint PRIMARY KEY) ON COMMIT DROP;
    CREATE TEMP TABLE affected_ways (id bigint PRIMARY KEY) ON COMMIT DROP;
    CREATE TEMP TABLE dropped_edges (source bigint, target bigint) ON COMMIT DROP;
"""

CLAIM_WAYS = """
    WITH claimed AS (
        DELETE FROM graph.pending_ways
        WHERE way_id IN (
            SELECT way_id FROM graph.pending_ways ORDER BY way_id LIMIT %(batch_size)s
        )
        RETURNING way_id
    )
    INSERT INTO claimed_ways SELECT way_id FROM claimed
"""

CLAIM_NODES = """
    WITH claimed AS (
        DELETE FROM graph.pending_nodes
        WHERE node_id IN (
            SELECT node_id FROM graph.pending_nodes ORDER BY node_id LIMIT %(batch_size)s
        )
        RETURNING node_id
    )
    INSERT INTO moved_nodes SELECT node_id FROM claimed
"""

# The claimed ways, and every way sharing a node with them before or after the change, since
# their split points may have moved. A way's old nodes that were split points are the ends of
# its current edges; its other old nodes were used by no other routable way.
FIND_AFFECTED_WAYS = """
    WITH seed AS (
        SELECT unnest(w.node_ids) AS id FROM raw.osm_ways w JOIN claimed_ways c USING (id)
        UNION SELECT e.source FROM graph.edges e JOIN claimed_ways c ON c.id = e.way_id
        UNION SELECT e.target FROM graph.edges e JOIN claimed_ways c ON c.id = e.way_id
        UNION SELECT id FROM moved_nodes
    )
    INSERT INTO affected_ways
    SELECT id FROM claimed_ways
    UNION
    SELECT w.id FROM seed s JOIN raw.osm_ways w ON w.node_ids @> ARRAY[s.id]
"""

# Every way that uses a node of an affected way, with the activities allowed in each direction.
# Only routable ways are kept; they decide where the affected ways are split.
CLASSIFY_WAYS = """
    CREATE TEMP TABLE routable_ways ON COMMIT DROP AS
    WITH affected_nodes AS (
        SELECT DISTINCT n.id
        FROM raw.osm_ways w JOIN affected_ways USING (id), unnest(w.node_ids) AS n(id)
    ),
    context AS (
        SELECT
            w.id,
            w.tags,
            -- A node repeated back to back is a data glitch, not a crossing.
            ARRAY(
                SELECT p.id FROM (
                    SELECT u.id, u.pos, lag(u.id) OVER (ORDER BY u.pos) AS previous_id
                    FROM unnest(w.node_ids) WITH ORDINALITY AS u(id, pos)
                ) p
                WHERE p.previous_id IS DISTINCT FROM p.id
                ORDER BY p.pos
            ) AS node_ids
        FROM raw.osm_ways w
        WHERE w.id IN (
            SELECT c.id FROM affected_nodes n JOIN raw.osm_ways c ON c.node_ids @> ARRAY[n.id]
        )
    ),
    rules AS (
        SELECT
            w.id,
            act.code,
            CASE
                WHEN coalesce(w.tags ->> act.access_key, w.tags ->> 'access')
                    IN ('no', 'private', 'use_sidepath') THEN false
                WHEN w.tags ->> act.access_key IN ('yes', 'designated', 'permissive') THEN true
                ELSE EXISTS (
                    SELECT 1 FROM ref.activity_highways h
                    WHERE h.activity = act.code
                      AND h.highway = coalesce(w.tags ->> 'highway', 'ferry')
                )
            END AS allowed,
            CASE
                WHEN w.tags ? act.oneway_key THEN w.tags ->> act.oneway_key
                WHEN act.follows_oneway THEN coalesce(
                    w.tags ->> 'oneway',
                    CASE WHEN w.tags ->> 'junction' IN ('roundabout', 'circular') THEN 'yes' END
                )
            END AS oneway
        FROM context w CROSS JOIN ref.activities act
        WHERE (w.tags ? 'highway' OR w.tags ->> 'route' = 'ferry')
          AND w.tags ->> 'area' IS DISTINCT FROM 'yes'
    ),
    access AS (
        SELECT
            id,
            coalesce(array_agg(code ORDER BY code) FILTER (
                WHERE allowed AND oneway IS DISTINCT FROM '-1' AND oneway IS DISTINCT FROM 'reverse'
            ), '{}') AS forward,
            coalesce(array_agg(code ORDER BY code) FILTER (
                WHERE allowed AND oneway IS DISTINCT FROM 'yes' AND oneway IS DISTINCT FROM 'true'
                  AND oneway IS DISTINCT FROM '1'
            ), '{}') AS backward
        FROM rules
        GROUP BY id
    )
    SELECT c.id, c.tags, c.node_ids, a.forward, a.backward
    FROM context c JOIN access a USING (id)
    WHERE cardinality(a.forward) + cardinality(a.backward) > 0
"""

# Affected routable ways cut at shared nodes and at their ends. A node used more than once by
# the same way (a self-crossing) counts as shared too. Ways with a node missing from raw or
# fewer than two nodes are left out.
BUILD_SEGMENTS = """
    CREATE TEMP TABLE segments ON COMMIT DROP AS
    WITH build AS (
        SELECT r.* FROM routable_ways r JOIN affected_ways USING (id)
        WHERE cardinality(r.node_ids) >= 2
          AND NOT EXISTS (
              SELECT 1 FROM unnest(r.node_ids) AS n(id)
              WHERE NOT EXISTS (SELECT 1 FROM raw.osm_nodes o WHERE o.id = n.id)
          )
    ),
    uses AS (
        SELECT n.id, count(*) AS uses
        FROM routable_ways r, unnest(r.node_ids) AS n(id)
        WHERE n.id IN (SELECT unnest(node_ids) FROM build)
        GROUP BY n.id
    ),
    points AS (
        SELECT b.id AS way_id, p.pos, p.node_id,
               p.pos = 1 OR p.pos = cardinality(b.node_ids) AS is_end,
               p.pos = cardinality(b.node_ids) AS is_last
        FROM build b, unnest(b.node_ids) WITH ORDINALITY AS p(node_id, pos)
    ),
    splits AS (
        SELECT p.*, p.is_end OR u.uses > 1 AS is_split,
               coalesce(sum((p.is_end OR u.uses > 1)::int) OVER (
                   PARTITION BY p.way_id ORDER BY p.pos
                   ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
               ), 0) AS splits_before
        FROM points p JOIN uses u ON u.id = p.node_id
    ),
    -- A split point ends one segment and starts the next.
    members AS (
        SELECT way_id, pos, node_id, splits_before AS seg FROM splits WHERE splits_before >= 1
        UNION ALL
        SELECT way_id, pos, node_id, splits_before + 1 FROM splits WHERE is_split AND NOT is_last
    ),
    lines AS (
        SELECT m.way_id, m.seg,
               (array_agg(m.node_id ORDER BY m.pos))[1] AS source,
               (array_agg(m.node_id ORDER BY m.pos DESC))[1] AS target,
               ST_MakeLine(array_agg(o.geom ORDER BY m.pos)) AS geom
        FROM members m JOIN raw.osm_nodes o ON o.id = m.node_id
        GROUP BY m.way_id, m.seg
    )
    SELECT l.way_id, l.seg, l.source, l.target,
           row_number() OVER (PARTITION BY l.way_id, l.source, l.target ORDER BY l.seg)
               AS occurrence,
           l.geom, ST_Length(l.geom::geography) AS length_m, b.tags, b.forward, b.backward
    FROM lines l JOIN build b ON b.id = l.way_id
"""

COUNT_SKIPPED_WAYS = """
    SELECT count(*) FROM routable_ways r JOIN affected_ways USING (id)
    WHERE NOT EXISTS (SELECT 1 FROM segments s WHERE s.way_id = r.id)
"""

CLASSIFY_CHANGES = """
    CREATE TEMP TABLE segment_changes ON COMMIT DROP AS
    SELECT s.*, e.id AS edge_id,
           CASE
               WHEN e.id IS NULL THEN 'new'
               WHEN e.geom IS DISTINCT FROM s.geom THEN 'moved'
               WHEN (e.forward, e.backward) IS DISTINCT FROM (s.forward, s.backward) THEN 'access'
               ELSE 'same'
           END AS change
    FROM segments s
    LEFT JOIN graph.edges e USING (way_id, source, target, occurrence)
"""

# Existing ways whose tags changed; their edges keep geometry but lose their scores.
FIND_RETAGGED_WAYS = """
    CREATE TEMP TABLE retagged_ways ON COMMIT DROP AS
    SELECT g.id FROM graph.ways g
    JOIN (SELECT DISTINCT way_id, tags FROM segments) s ON s.way_id = g.id
    WHERE g.tags IS DISTINCT FROM s.tags
"""

UPSERT_WAYS = """
    INSERT INTO graph.ways AS existing (id, tags)
    SELECT DISTINCT way_id, tags FROM segments
    ON CONFLICT (id) DO UPDATE SET tags = EXCLUDED.tags
    WHERE existing.tags IS DISTINCT FROM EXCLUDED.tags
"""

UPSERT_VERTICES = """
    INSERT INTO graph.vertices AS existing (id, geom)
    SELECT o.id, o.geom FROM raw.osm_nodes o
    WHERE o.id IN (SELECT source FROM segments UNION SELECT target FROM segments)
    ON CONFLICT (id) DO UPDATE SET geom = EXCLUDED.geom
    WHERE existing.geom IS DISTINCT FROM EXCLUDED.geom
"""

DELETE_STALE_EDGES = """
    WITH deleted AS (
        DELETE FROM graph.edges e
        USING affected_ways a
        WHERE e.way_id = a.id
          AND NOT EXISTS (
              SELECT 1 FROM segments s
              WHERE (s.way_id, s.source, s.target, s.occurrence)
                  = (e.way_id, e.source, e.target, e.occurrence)
          )
        RETURNING e.source, e.target
    )
    INSERT INTO dropped_edges SELECT source, target FROM deleted
"""

UPDATE_EDGES = """
    UPDATE graph.edges e
    SET geom = c.geom, length_m = c.length_m, forward = c.forward, backward = c.backward,
        scores = CASE WHEN c.change = 'moved' THEN '{}' ELSE e.scores END
    FROM segment_changes c
    WHERE e.id = c.edge_id AND c.change IN ('moved', 'access')
"""

# Ordered so a rebuild numbers new edges the same way every time.
INSERT_EDGES = """
    WITH inserted AS (
        INSERT INTO graph.edges
            (way_id, source, target, occurrence, geom, length_m, forward, backward)
        SELECT way_id, source, target, occurrence, geom, length_m, forward, backward
        FROM segment_changes WHERE change = 'new'
        ORDER BY way_id, seg
        RETURNING id
    )
    INSERT INTO graph.pending_edges SELECT id FROM inserted
"""

QUEUE_CHANGED_EDGES = """
    WITH retagged AS (
        UPDATE graph.edges SET scores = '{}'
        WHERE way_id IN (SELECT id FROM retagged_ways)
        RETURNING id
    )
    INSERT INTO graph.pending_edges
    SELECT id FROM retagged
    UNION SELECT edge_id FROM segment_changes WHERE change = 'moved'
    ON CONFLICT DO NOTHING
"""

DELETE_UNROUTABLE_WAYS = """
    DELETE FROM graph.ways g USING affected_ways a
    WHERE g.id = a.id AND NOT EXISTS (SELECT 1 FROM segments s WHERE s.way_id = g.id)
"""

DELETE_UNUSED_VERTICES = """
    DELETE FROM graph.vertices v
    WHERE v.id IN (SELECT source FROM dropped_edges UNION SELECT target FROM dropped_edges)
      AND NOT EXISTS (SELECT 1 FROM graph.edges e WHERE e.source = v.id OR e.target = v.id)
"""
