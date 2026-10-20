-- User data, written by wayted_api.

CREATE TABLE app.users (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
	-- email needs to be lowercased before insertion
    email         text NOT NULL UNIQUE CHECK (email = lower(email)),
    name          text NOT NULL CHECK (name <> ''),
    password_hash text NOT NULL,
    language      text NOT NULL DEFAULT 'en' CHECK (language ~ '^[a-z]{2}$'),
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.refresh_tokens (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
    -- hex SHA-256 of the token
    token_hash text NOT NULL UNIQUE,
    issued_at  timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    CONSTRAINT refresh_tokens_expires_after_issued_check CHECK (expires_at > issued_at)
);

CREATE INDEX refresh_tokens_user_id_idx ON app.refresh_tokens (user_id);
CREATE INDEX refresh_tokens_expires_at_idx ON app.refresh_tokens (expires_at);

-- A saved route. The geometry is what the user saw and stays the truth; the edges are how it ran
-- through the graph when it was saved.
CREATE TABLE app.routes (
    id                bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id           uuid    NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
    name              text    NOT NULL CHECK (char_length(name) BETWEEN 1 AND 80),
    -- the request the route was planned from
    activity          text    NOT NULL REFERENCES ref.activities (code),
    shape             text    NOT NULL CHECK (shape IN ('loop', 'point_to_point')),
    target_distance_m integer NOT NULL CHECK (target_distance_m > 0),
    preferences       jsonb   NOT NULL DEFAULT '{}',
    -- derived from the edges when saved, then frozen
    geom              geometry(LineString, 4326) NOT NULL,
    distance_m        double precision NOT NULL CHECK (distance_m >= 0),
    -- {attribute: {"mean": 0..1, "coverage": share of the length that was scored}}
    scores            jsonb   NOT NULL DEFAULT '{}',
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX routes_user_id_idx ON app.routes (user_id, created_at DESC);

-- No foreign key to graph.edges here or in segment_review_edges: a reimport can split or delete
-- an edge, and that must not delete user data.
CREATE TABLE app.route_edges (
    route_id   bigint  NOT NULL REFERENCES app.routes (id) ON DELETE CASCADE,
    seq        integer NOT NULL CHECK (seq >= 0),
    edge_id    bigint  NOT NULL,
    -- whether the route runs from source to target
    forward    boolean NOT NULL,
    length_m   double precision NOT NULL CHECK (length_m >= 0),
    -- index in routes.geom of the point the edge ends at; it starts where the edge before ends
    last_point integer NOT NULL CHECK (last_point >= 1),
    PRIMARY KEY (route_id, seq)
);

CREATE TABLE app.route_reviews (
    user_id    uuid   NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
    route_id   bigint NOT NULL REFERENCES app.routes (id) ON DELETE CASCADE,
    comment    text   CHECK (char_length(comment) BETWEEN 1 AND 500),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, route_id)
);

CREATE INDEX route_reviews_route_id_idx ON app.route_reviews (route_id);

CREATE TABLE app.route_review_answers (
    user_id   uuid     NOT NULL,
    route_id  bigint   NOT NULL,
    attribute text     NOT NULL REFERENCES ref.attributes (key),
    -- -1 wanted less, 0 about right, 1 wanted more
    answer    smallint NOT NULL CHECK (answer BETWEEN -1 AND 1),
    PRIMARY KEY (user_id, route_id, attribute),
    FOREIGN KEY (user_id, route_id) REFERENCES app.route_reviews (user_id, route_id)
        ON DELETE CASCADE
);

-- The user's default weights; an attribute without a row is "don't mind".
CREATE TABLE app.user_preferences (
    user_id   uuid         NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
    attribute text         NOT NULL REFERENCES ref.attributes (key),
    weight    numeric(3,2) NOT NULL CHECK (weight BETWEEN -1 AND 1 AND weight <> 0),
    PRIMARY KEY (user_id, attribute)
);

CREATE TABLE app.segment_reviews (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    uuid   NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
    -- kept when the route is deleted: the review is about the road
    route_id   bigint REFERENCES app.routes (id) ON DELETE SET NULL,
    activity   text   NOT NULL REFERENCES ref.activities (code),
    -- the stretch as reviewed
    geom       geometry(LineString, 4326) NOT NULL,
    comment    text   CHECK (char_length(comment) BETWEEN 1 AND 500),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX segment_reviews_user_id_idx ON app.segment_reviews (user_id);
CREATE INDEX segment_reviews_route_id_idx ON app.segment_reviews (route_id);

CREATE TABLE app.segment_review_edges (
    review_id bigint NOT NULL REFERENCES app.segment_reviews (id) ON DELETE CASCADE,
    edge_id   bigint NOT NULL,
    PRIMARY KEY (review_id, edge_id)
);

CREATE INDEX segment_review_edges_edge_id_idx ON app.segment_review_edges (edge_id);

CREATE TABLE app.segment_review_reasons (
    review_id bigint NOT NULL REFERENCES app.segment_reviews (id) ON DELETE CASCADE,
    reason    text   NOT NULL REFERENCES ref.review_reasons (code),
    PRIMARY KEY (review_id, reason)
);

-- The enricher counts segment reviews into graph.edges.feedback; these triggers queue the edges
-- whose votes changed, whichever way the change came. Edges no longer in the graph are skipped.
CREATE FUNCTION app.queue_edges() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO graph.pending_edges (edge_id)
    SELECT DISTINCT e.id FROM changed c JOIN graph.edges e ON e.id = c.edge_id;
    RETURN NULL;
END
$$;

CREATE FUNCTION app.queue_review_edges() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO graph.pending_edges (edge_id)
    SELECT DISTINCT e.id
    FROM (SELECT DISTINCT review_id FROM changed) c
    JOIN app.segment_review_edges r ON r.review_id = c.review_id
    JOIN graph.edges e ON e.id = r.edge_id;
    RETURN NULL;
END
$$;

CREATE TRIGGER segment_review_edges_insert_queue
    AFTER INSERT ON app.segment_review_edges REFERENCING NEW TABLE AS changed
    FOR EACH STATEMENT EXECUTE FUNCTION app.queue_edges();

-- A deleted review cascades here; its reasons may already be gone.
CREATE TRIGGER segment_review_edges_delete_queue
    AFTER DELETE ON app.segment_review_edges REFERENCING OLD TABLE AS changed
    FOR EACH STATEMENT EXECUTE FUNCTION app.queue_edges();

CREATE TRIGGER segment_review_reasons_insert_queue
    AFTER INSERT ON app.segment_review_reasons REFERENCING NEW TABLE AS changed
    FOR EACH STATEMENT EXECUTE FUNCTION app.queue_review_edges();

CREATE TRIGGER segment_review_reasons_delete_queue
    AFTER DELETE ON app.segment_review_reasons REFERENCING OLD TABLE AS changed
    FOR EACH STATEMENT EXECUTE FUNCTION app.queue_review_edges();
