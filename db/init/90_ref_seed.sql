-- Rows for the ref lookup tables.
INSERT INTO ref.source_layers (code, zoom, ttl) VALUES
    ('roads', 14, '1 month'),
    ('green_areas', 14, '1 month'),
    ('parks', 14, '1 month'),
    ('nature', 14, '1 month');

INSERT INTO ref.activities (code, access_key, oneway_key, follows_oneway) VALUES
    ('running', 'foot', 'oneway:foot', false),
    ('cycling', 'bicycle', 'oneway:bicycle', true);

-- Motorways and trunks are left out for both.
INSERT INTO ref.activity_highways (activity, highway)
SELECT 'running', unnest(ARRAY[
    'footway', 'path', 'pedestrian', 'steps', 'track', 'bridleway', 'living_street',
    'residential', 'service', 'unclassified', 'tertiary', 'tertiary_link', 'secondary',
    'secondary_link', 'primary', 'primary_link', 'cycleway', 'ferry'
])
UNION ALL
SELECT 'cycling', unnest(ARRAY[
    'cycleway', 'path', 'track', 'living_street', 'residential', 'service', 'unclassified',
    'tertiary', 'tertiary_link', 'secondary', 'secondary_link', 'primary', 'primary_link',
    'ferry'
]);
