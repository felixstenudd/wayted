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
-- non-auth

CREATE TYPE app.route_type AS ENUM (
    'loop',
    'out_and_back',
    'point_to_point'
);


CREATE TABLE app.route (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES app.user(id),

    name text,
    activity_id bigint NOT NULL REFERENCES ref.activity(id),

    route_type app.route_type NOT NULL,

    distance_m double precision NOT NULL
        CHECK (distance_m >= 0),

    geom geometry(LineString, 4326) NOT NULL,

    is_public boolean NOT NULL DEFAULT false,

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX route_user_idx
    ON app.route(user_id);

CREATE INDEX route_geom_idx
    ON app.route USING gist (geom);

CREATE INDEX route_public_activity_idx
    ON app.route(activity_id, created_at DESC)
    WHERE is_public = true;


CREATE TABLE app.route_save (
    user_id bigint NOT NULL
        REFERENCES app.user(id) ON DELETE CASCADE,

    route_id bigint NOT NULL
        REFERENCES app.route(id) ON DELETE CASCADE,

    created_at timestamptz NOT NULL DEFAULT now(),

    PRIMARY KEY (user_id, route_id)
);

CREATE INDEX route_save_route_idx
    ON app.route_save(route_id);


CREATE TABLE app.route_review (
    user_id bigint NOT NULL
        REFERENCES app.user(id) ON DELETE CASCADE,

    route_id bigint NOT NULL
        REFERENCES app.route(id) ON DELETE CASCADE,

    rating smallint NOT NULL
        CHECK (rating BETWEEN 1 AND 5),

    comment text,

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    PRIMARY KEY (user_id, route_id)
);

CREATE INDEX route_review_route_idx
    ON app.route_review(route_id);


CREATE TABLE app.segment_rating (
    user_id bigint NOT NULL
        REFERENCES app.user(id) ON DELETE CASCADE,

    segment_id bigint NOT NULL
        REFERENCES graph.segment(id),

    rating smallint NOT NULL
        CHECK (rating BETWEEN 1 AND 5),

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    PRIMARY KEY (user_id, segment_id)
);

CREATE INDEX segment_rating_segment_idx
    ON app.segment_rating(segment_id);