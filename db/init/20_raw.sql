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

CREATE TABLE raw.osm_relations (
    id      bigint PRIMARY KEY,
    tags    jsonb  NOT NULL,
    -- [{"type": "way", "ref": 123, "role": "outer"}, ...] in relation order
    members jsonb  NOT NULL
);
