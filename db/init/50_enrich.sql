-- Feature geometry built from raw by wayted_enricher, to score graph.edges.

-- Area features of every area layer, from closed ways and multipolygon relations.
CREATE TABLE enrich.areas (
    -- a FeatureLayer code
    layer    text   NOT NULL,
    osm_type text   NOT NULL CHECK (osm_type IN ('way', 'relation')),
    osm_id   bigint NOT NULL,
    tags     jsonb  NOT NULL,
    geom     geometry(MultiPolygon, 4326) NOT NULL,
    PRIMARY KEY (layer, osm_type, osm_id)
);

CREATE INDEX areas_geom_idx ON enrich.areas USING gist (geom);

-- Line features of every line layer, from ways.
CREATE TABLE enrich.lines (
    -- a FeatureLayer code
    layer    text   NOT NULL,
    osm_type text   NOT NULL CHECK (osm_type = 'way'),
    osm_id   bigint NOT NULL,
    tags     jsonb  NOT NULL,
    geom     geometry(MultiLineString, 4326) NOT NULL,
    PRIMARY KEY (layer, osm_type, osm_id)
);

CREATE INDEX lines_geom_idx ON enrich.lines USING gist (geom);

-- The ways each feature is built from: itself for a way, its member ways for a relation. Kept
-- also when the feature could not be built, so a missing member arriving later finds it.
CREATE TABLE enrich.feature_ways (
    osm_type text   NOT NULL CHECK (osm_type IN ('way', 'relation')),
    osm_id   bigint NOT NULL,
    way_id   bigint NOT NULL,
    PRIMARY KEY (osm_type, osm_id, way_id)
);

CREATE INDEX feature_ways_way_id_idx ON enrich.feature_ways (way_id);

-- Append-only, like the graph queues: a row written by a download that is still open is
-- invisible to a running batch, which cannot claim it too early.
CREATE TABLE enrich.pending_ways (
    id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    way_id bigint NOT NULL
);

CREATE TABLE enrich.pending_relations (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    relation_id bigint NOT NULL
);

CREATE TABLE enrich.pending_nodes (
    id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    node_id bigint NOT NULL
);

-- The WGS 84 UTM zone of a geometry's centre, for measuring in metres anywhere.
CREATE FUNCTION enrich.utm_srid(geom geometry) RETURNS integer
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT CASE WHEN ST_Y(c) >= 0 THEN 32600 ELSE 32700 END
           + least(floor((ST_X(c) + 180) / 6)::integer + 1, 60)
    FROM ST_Centroid(geom) AS c
$$;

-- The bounding box of geom, grown by at least m metres on every side.
CREATE FUNCTION enrich.expand_m(geom geometry, m double precision) RETURNS geometry
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT ST_Expand(
        geom,
        m / (111319 * cos(radians(least(greatest(abs(ST_YMin(geom)), abs(ST_YMax(geom))), 89)))),
        m / 110574
    )
$$;

CREATE FUNCTION enrich.queue_way() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO enrich.pending_ways (way_id)
    VALUES (CASE WHEN TG_OP = 'DELETE' THEN OLD.id ELSE NEW.id END);
    RETURN NULL;
END
$$;

CREATE TRIGGER osm_ways_enrich_queue
    AFTER INSERT OR UPDATE OR DELETE ON raw.osm_ways
    FOR EACH ROW EXECUTE FUNCTION enrich.queue_way();

CREATE FUNCTION enrich.queue_relation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO enrich.pending_relations (relation_id)
    VALUES (CASE WHEN TG_OP = 'DELETE' THEN OLD.id ELSE NEW.id END);
    RETURN NULL;
END
$$;

CREATE TRIGGER osm_relations_enrich_queue
    AFTER INSERT OR UPDATE OR DELETE ON raw.osm_relations
    FOR EACH ROW EXECUTE FUNCTION enrich.queue_relation();

-- A new node changes nothing until a way uses it, and that way is queued.
CREATE FUNCTION enrich.queue_node() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO enrich.pending_nodes (node_id) VALUES (NEW.id);
    RETURN NULL;
END
$$;

CREATE TRIGGER osm_nodes_enrich_queue
    AFTER UPDATE OF geom ON raw.osm_nodes
    FOR EACH ROW WHEN (OLD.geom IS DISTINCT FROM NEW.geom)
    EXECUTE FUNCTION enrich.queue_node();

-- Wakes the enricher. Sent at commit, and once per transaction however many rows it queued.
CREATE FUNCTION enrich.notify_pending() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NOTIFY pending_enrichment;
    RETURN NULL;
END
$$;

CREATE TRIGGER pending_edges_notify
    AFTER INSERT ON graph.pending_edges
    FOR EACH STATEMENT EXECUTE FUNCTION enrich.notify_pending();

CREATE TRIGGER pending_ways_notify
    AFTER INSERT ON enrich.pending_ways
    FOR EACH STATEMENT EXECUTE FUNCTION enrich.notify_pending();

CREATE TRIGGER pending_relations_notify
    AFTER INSERT ON enrich.pending_relations
    FOR EACH STATEMENT EXECUTE FUNCTION enrich.notify_pending();

CREATE TRIGGER pending_nodes_notify
    AFTER INSERT ON enrich.pending_nodes
    FOR EACH STATEMENT EXECUTE FUNCTION enrich.notify_pending();
