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
