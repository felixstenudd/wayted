-- Lookup tables: attributes, activities. Rows are inserted in 90_ref_seed.sql.

CREATE TABLE ref.source_layers (
    code text PRIMARY KEY CHECK (code ~ '^[a-z][a-z_]*$'),
    -- web mercator zoom the layer is fetched at
    zoom smallint NOT NULL CHECK (zoom BETWEEN 0 AND 22),
    ttl  interval NOT NULL CHECK (ttl > interval '0')
);

CREATE TABLE ref.activities (
    code           text    PRIMARY KEY CHECK (code ~ '^[a-z][a-z_]*$'),
    -- OSM key that allows or forbids the activity, e.g. foot
    access_key     text    NOT NULL,
    -- one-way tag for this activity only, e.g. oneway:foot; always respected
    oneway_key     text    NOT NULL,
    -- whether oneway and junction=roundabout apply
    follows_oneway boolean NOT NULL
);

-- Highway values an activity may use unless the way's tags say otherwise. Ferries (route=ferry
-- without a highway tag) count as the value 'ferry'.
CREATE TABLE ref.activity_highways (
    activity text NOT NULL REFERENCES ref.activities (code),
    highway  text NOT NULL,
    PRIMARY KEY (activity, highway)
);
