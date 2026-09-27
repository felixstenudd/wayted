-- Lookup tables: attributes, activities. Rows are inserted in 90_ref_seed.sql.

CREATE TABLE ref.source_layers (
    code text PRIMARY KEY CHECK (code ~ '^[a-z][a-z_]*$'),
    -- web mercator zoom the layer is fetched at
    zoom smallint NOT NULL CHECK (zoom BETWEEN 0 AND 22),
    ttl  interval NOT NULL CHECK (ttl > interval '0')
);
