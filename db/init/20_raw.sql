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
