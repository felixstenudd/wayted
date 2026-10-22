"""SQL for one enricher batch, shared by every layer and attribute, in the order it runs."""

CREATE_WORK_TABLES = """
    CREATE TEMP TABLE claimed_ways (id bigint PRIMARY KEY) ON COMMIT DROP;
    CREATE TEMP TABLE claimed_relations (id bigint PRIMARY KEY) ON COMMIT DROP;
    CREATE TEMP TABLE moved_nodes (id bigint PRIMARY KEY) ON COMMIT DROP;
    CREATE TEMP TABLE feature_candidates (
        osm_type text, osm_id bigint, PRIMARY KEY (osm_type, osm_id)
    ) ON COMMIT DROP;
    CREATE TEMP TABLE changed_features (layer text NOT NULL, geom geometry NOT NULL) ON COMMIT DROP;
    CREATE TEMP TABLE claimed_edges (id bigint PRIMARY KEY) ON COMMIT DROP;
    CREATE TEMP TABLE changed_elevation (
        z smallint, x int, y int, PRIMARY KEY (z, x, y)
    ) ON COMMIT DROP;
"""

# Claims queue rows, not ids: an element queued again by a download that is still open keeps its
# newer row for the next batch.
CLAIM_WAYS = """
    WITH claimed AS (
        DELETE FROM enrich.pending_ways
        WHERE id IN (SELECT id FROM enrich.pending_ways ORDER BY id LIMIT %(batch_size)s)
        RETURNING way_id
    )
    INSERT INTO claimed_ways SELECT DISTINCT way_id FROM claimed
"""

CLAIM_RELATIONS = """
    WITH claimed AS (
        DELETE FROM enrich.pending_relations
        WHERE id IN (SELECT id FROM enrich.pending_relations ORDER BY id LIMIT %(batch_size)s)
        RETURNING relation_id
    )
    INSERT INTO claimed_relations SELECT DISTINCT relation_id FROM claimed
"""

CLAIM_NODES = """
    WITH claimed AS (
        DELETE FROM enrich.pending_nodes
        WHERE id IN (SELECT id FROM enrich.pending_nodes ORDER BY id LIMIT %(batch_size)s)
        RETURNING node_id
    )
    INSERT INTO moved_nodes SELECT DISTINCT node_id FROM claimed
"""

CLAIM_ELEVATION = """
    WITH claimed AS (
        DELETE FROM enrich.pending_elevation
        WHERE id IN (SELECT id FROM enrich.pending_elevation ORDER BY id LIMIT %(batch_size)s)
        RETURNING z, x, y
    )
    INSERT INTO changed_elevation SELECT DISTINCT z, x, y FROM claimed
"""

# Each claimed element itself, and the features built from a claimed way or a way through a
# moved node.
FIND_CANDIDATES = """
    INSERT INTO feature_candidates
    SELECT 'way', id FROM claimed_ways
    UNION SELECT 'relation', id FROM claimed_relations
    UNION
    SELECT f.osm_type, f.osm_id FROM enrich.feature_ways f JOIN claimed_ways c ON c.id = f.way_id
    UNION
    SELECT f.osm_type, f.osm_id
    FROM moved_nodes n
    JOIN raw.osm_ways w ON w.node_ids @> ARRAY[n.id]
    JOIN enrich.feature_ways f ON f.way_id = w.id
"""

# Every layer writes the dependencies of the candidates it still matches.
FORGET_FEATURE_WAYS = """
    DELETE FROM enrich.feature_ways f USING feature_candidates c
    WHERE (f.osm_type, f.osm_id) = (c.osm_type, c.osm_id)
"""

# Edges whose score a changed feature may have changed: those within reach_m of its old or new
# geometry. The box around the edge is at least reach_m wide, so a few more are queued than
# needed, which only costs a rescore.
QUEUE_NEAR_CHANGED = """
    INSERT INTO graph.pending_edges (edge_id)
    SELECT DISTINCT e.id
    FROM changed_features c
    JOIN graph.edges e ON e.geom && enrich.expand_m(c.geom, %(reach_m)s)
    WHERE c.layer = %(layer)s AND ST_Intersects(c.geom, enrich.expand_m(e.geom, %(reach_m)s))
"""

# Edges whose heights a changed elevation tile may have changed: those whose box meets it.
QUEUE_ON_CHANGED_ELEVATION = """
    INSERT INTO graph.pending_edges (edge_id)
    SELECT DISTINCT e.id
    FROM changed_elevation t
    JOIN graph.edges e ON e.geom && ST_Transform(ST_TileEnvelope(t.z, t.x, t.y), 4326)
"""

CLAIM_EDGES = """
    WITH claimed AS (
        DELETE FROM graph.pending_edges
        WHERE id IN (SELECT id FROM graph.pending_edges ORDER BY id LIMIT %(batch_size)s)
        RETURNING edge_id
    )
    INSERT INTO claimed_edges SELECT DISTINCT edge_id FROM claimed
"""

HAS_PENDING_EDGES = "SELECT EXISTS (SELECT 1 FROM graph.pending_edges)"

# An attribute's query goes between the two, as the subquery s. A NULL value leaves the key out.
MERGE_SCORES_HEAD = """
    UPDATE graph.edges e
    SET scores = CASE WHEN s.value IS NULL THEN e.scores - %(key)s::text
                      ELSE e.scores || jsonb_build_object(%(key)s::text, s.value) END
    FROM (
"""

MERGE_SCORES_TAIL = """
    ) s
    WHERE e.id = s.edge_id
"""

# Users' segment reviews of the claimed edges as votes per activity and topic:
# {activity: {topic: {"up": n, "down": n}}}. A user counts once per edge, activity and topic,
# with the latest of their reviews that says something on that topic.
COUNT_FEEDBACK = """
    WITH votes AS (
        SELECT DISTINCT ON (s.user_id, re.edge_id, s.activity, r.topic)
               re.edge_id, s.activity, r.topic, r.sentiment
        FROM claimed_edges c
        JOIN app.segment_review_edges re ON re.edge_id = c.id
        JOIN app.segment_reviews s ON s.id = re.review_id
        JOIN app.segment_review_reasons sr ON sr.review_id = s.id
        JOIN ref.review_reasons r ON r.code = sr.reason
        ORDER BY s.user_id, re.edge_id, s.activity, r.topic, s.updated_at DESC, s.id DESC
    ),
    topics AS (
        SELECT edge_id, activity, topic,
               jsonb_build_object(
                   'up', count(*) FILTER (WHERE sentiment = 1),
                   'down', count(*) FILTER (WHERE sentiment = -1)
               ) AS counts
        FROM votes
        GROUP BY edge_id, activity, topic
    ),
    activities AS (
        SELECT edge_id, activity, jsonb_object_agg(topic, counts) AS topics
        FROM topics
        GROUP BY edge_id, activity
    ),
    counted AS (
        SELECT c.id,
               coalesce(jsonb_object_agg(a.activity, a.topics) FILTER (WHERE a.edge_id IS NOT NULL),
                        '{}') AS feedback
        FROM claimed_edges c
        LEFT JOIN activities a ON a.edge_id = c.id
        GROUP BY c.id
    )
    UPDATE graph.edges e SET feedback = counted.feedback
    FROM counted
    WHERE e.id = counted.id AND e.feedback IS DISTINCT FROM counted.feedback
"""
