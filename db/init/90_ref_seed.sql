-- Rows for the ref lookup tables.
INSERT INTO ref.source_layers (code, zoom, ttl) VALUES
    ('roads', 14, '1 month'),
    ('green_areas', 14, '1 month'),
    ('parks', 14, '1 month'),
    ('nature', 14, '1 month'),
    ('water', 14, '1 month'),
    ('water_lines', 14, '1 month');

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

INSERT INTO ref.attributes (key) VALUES
    ('green'), ('nature'), ('water'), ('quiet_streets'), ('sights'), ('bridges'), ('prepared');

INSERT INTO ref.review_reasons (code, topic, sentiment, attribute) VALUES
    ('green_bad', 'green', -1, 'green'),
    ('green_good', 'green', 1, 'green'),
    ('nature_bad', 'nature', -1, 'nature'),
    ('nature_good', 'nature', 1, 'nature'),
    ('water_bad', 'water', -1, 'water'),
    ('water_good', 'water', 1, 'water'),
    ('quiet_streets_bad', 'quiet_streets', -1, 'quiet_streets'),
    ('quiet_streets_good', 'quiet_streets', 1, 'quiet_streets'),
    ('sights_bad', 'sights', -1, 'sights'),
    ('sights_good', 'sights', 1, 'sights'),
    ('prepared_bad', 'prepared', -1, 'prepared'),
    ('prepared_good', 'prepared', 1, 'prepared'),
    ('elevation_bad', 'elevation', -1, NULL),
    ('elevation_good', 'elevation', 1, NULL),
    ('lighting_bad', 'lighting', -1, NULL),
    ('lighting_good', 'lighting', 1, NULL),
    ('safety_bad', 'safety', -1, NULL),
    ('safety_good', 'safety', 1, NULL),
    ('crowding_bad', 'crowding', -1, NULL),
    ('access_bad', 'access', -1, NULL);
