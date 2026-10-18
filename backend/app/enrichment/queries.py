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
