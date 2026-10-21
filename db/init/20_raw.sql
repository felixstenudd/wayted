-- Downloaded source data, written by wayted_downloader.

CREATE TABLE raw.fetched_tiles (
    layer      text        NOT NULL REFERENCES ref.source_layers (code),
    z          smallint    NOT NULL CHECK (z BETWEEN 0 AND 22),
    x          int         NOT NULL,
    y          int         NOT NULL,
    fetched_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    PRIMARY KEY (layer, z, x, y),
    CONSTRAINT fetched_tiles_xy_in_zoom_check CHECK (x >= 0 AND x < (1 << z) AND y >= 0 AND y < (1 << z)),
    CONSTRAINT fetched_tiles_expires_after_fetched_check CHECK (expires_at > fetched_at)
);

-- Tiles waiting to be fetched and mapped, row is deleted once its tile is mapped.
CREATE TABLE raw.pending_tiles (
    layer           text        NOT NULL REFERENCES ref.source_layers (code),
    z               smallint    NOT NULL CHECK (z BETWEEN 0 AND 22),
    x               int         NOT NULL,
    y               int         NOT NULL,
    requested_at    timestamptz NOT NULL DEFAULT now(),
    status          text        NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'running', 'failed')),
    attempts        smallint    NOT NULL DEFAULT 0,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    last_status     text,
    last_message    text,
    PRIMARY KEY (layer, z, x, y),
    CONSTRAINT pending_tiles_xy_in_zoom_check CHECK (x >= 0 AND x < (1 << z) AND y >= 0 AND y < (1 << z))
);

-- Wakes the worker.
CREATE FUNCTION raw.notify_pending_tiles() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NOTIFY pending_tiles;
    RETURN NULL;
END
$$;

CREATE TRIGGER pending_tiles_notify
    AFTER INSERT ON raw.pending_tiles
    FOR EACH STATEMENT EXECUTE FUNCTION raw.notify_pending_tiles();

-- OSM elements as Overpass returns them, shared by every OSM layer. Which layer a row belongs to
-- is decided by its tags when it is read. Only node coordinates are converted, to a point.
CREATE TABLE raw.osm_nodes (
    id   bigint PRIMARY KEY,
    tags jsonb  NOT NULL,
    geom geometry(Point, 4326) NOT NULL
);

CREATE INDEX osm_nodes_geom_idx ON raw.osm_nodes USING gist (geom);

CREATE TABLE raw.osm_ways (
    id       bigint   PRIMARY KEY,
    tags     jsonb    NOT NULL,
    -- in way order; each id is a row in raw.osm_nodes
    node_ids bigint[] NOT NULL
);

CREATE INDEX osm_ways_node_ids_idx ON raw.osm_ways USING gin (node_ids);

-- Terrain heights in metres, one raster per tile of the elevation layer, cut from the source's
-- larger files. Each reaches one cell past its tile on every side, so a height sampled between
-- cells near the tile's edge has every neighbour it is blended from.
CREATE TABLE raw.elevation_tiles (
    z    smallint NOT NULL CHECK (z BETWEEN 0 AND 22),
    x    int      NOT NULL,
    y    int      NOT NULL,
    rast raster   NOT NULL,
    PRIMARY KEY (z, x, y),
    CONSTRAINT elevation_tiles_xy_in_zoom_check CHECK (x >= 0 AND x < (1 << z) AND y >= 0 AND y < (1 << z))
);

CREATE INDEX elevation_tiles_rast_idx ON raw.elevation_tiles USING gist (ST_ConvexHull(rast));

CREATE TABLE raw.osm_relations (
    id      bigint PRIMARY KEY,
    tags    jsonb  NOT NULL,
    -- [{"type": "way", "ref": 123, "role": "outer"}, ...] in relation order
    members jsonb  NOT NULL
);
