-- Routable network, built from raw by wayted_mapper and read by pgRouting.

-- Routable ways currently in the graph, with their tags for the enricher and the API.
CREATE TABLE graph.ways (
    id   bigint PRIMARY KEY,
    tags jsonb  NOT NULL
);

-- Edge ends; the id is the OSM node id.
CREATE TABLE graph.vertices (
    id   bigint PRIMARY KEY,
    geom geometry(Point, 4326) NOT NULL
);

CREATE INDEX vertices_geom_idx ON graph.vertices USING gist (geom);

CREATE TABLE graph.edges (
    id         bigint           GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    way_id     bigint           NOT NULL REFERENCES graph.ways (id) ON DELETE CASCADE,
    -- in way order
    source     bigint           NOT NULL REFERENCES graph.vertices (id),
    target     bigint           NOT NULL REFERENCES graph.vertices (id),
    -- when the way runs from source to target more than once
    occurrence smallint         NOT NULL CHECK (occurrence >= 1),
    geom       geometry(LineString, 4326) NOT NULL,
    length_m   double precision NOT NULL CHECK (length_m >= 0),
    -- ref.activities codes allowed from source to target, and back
    forward    text[]           NOT NULL,
    backward   text[]           NOT NULL,
    -- written by the enricher; '{}' until the edge is scored
    scores     jsonb            NOT NULL DEFAULT '{}',
    -- metres climbed and dropped from source to target, written by the enricher; NULL until it
    -- knows the heights
    ascent_m   double precision CHECK (ascent_m >= 0),
    descent_m  double precision CHECK (descent_m >= 0),
    -- users' segment reviews, counted by the enricher: {activity: {topic: {"up": n, "down": n}}}
    feedback   jsonb            NOT NULL DEFAULT '{}',
    CONSTRAINT edges_natural_key UNIQUE (way_id, source, target, occurrence),
    CONSTRAINT edges_routable_check CHECK (cardinality(forward) + cardinality(backward) > 0)
);

CREATE INDEX edges_geom_idx ON graph.edges USING gist (geom);
CREATE INDEX edges_source_idx ON graph.edges (source);
CREATE INDEX edges_target_idx ON graph.edges (target);

-- Work queues. The triggers below fill the first two from raw; the mapper fills the third for
-- the enricher. They are append-only, so an id can be queued more than once: a row written by a
-- download that is still open is invisible to a mapper batch, which cannot claim it too early.
CREATE TABLE graph.pending_ways (
    id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    way_id bigint NOT NULL
);

CREATE TABLE graph.pending_nodes (
    id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    node_id bigint NOT NULL
);

CREATE TABLE graph.pending_edges (
    id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    edge_id bigint NOT NULL REFERENCES graph.edges (id) ON DELETE CASCADE
);

CREATE INDEX pending_edges_edge_id_idx ON graph.pending_edges (edge_id);

-- Queue rows commit together with the raw change, so the mapper cannot miss one. The
-- downloader skips unchanged rows, so these fire only on real changes.
CREATE FUNCTION graph.queue_way() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO graph.pending_ways (way_id)
    VALUES (CASE WHEN TG_OP = 'DELETE' THEN OLD.id ELSE NEW.id END);
    RETURN NULL;
END
$$;

CREATE TRIGGER osm_ways_queue
    AFTER INSERT OR UPDATE OR DELETE ON raw.osm_ways
    FOR EACH ROW EXECUTE FUNCTION graph.queue_way();

-- A new node changes nothing until a way uses it, and that way is queued itself.
CREATE FUNCTION graph.queue_node() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO graph.pending_nodes (node_id) VALUES (NEW.id);
    RETURN NULL;
END
$$;

CREATE TRIGGER osm_nodes_queue
    AFTER UPDATE OF geom ON raw.osm_nodes
    FOR EACH ROW WHEN (OLD.geom IS DISTINCT FROM NEW.geom)
    EXECUTE FUNCTION graph.queue_node();
