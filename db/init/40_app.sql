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
