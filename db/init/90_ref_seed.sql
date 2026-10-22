-- Rows for the ref lookup tables.
INSERT INTO ref.source_layers (code, zoom, ttl) VALUES
    ('roads', 14, '1 month'),
    ('green_areas', 14, '1 month'),
    ('parks', 14, '1 month'),
    ('nature', 14, '1 month'),
    ('water', 14, '1 month'),
    ('water_lines', 14, '1 month'),
    -- Terrain hardly changes.
    ('elevation', 14, '1 year');

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

-- Busy roads cost more, so routes take them only when they save a lot, and a path beside a road
-- wins. A shared foot and cycle path (a cycleway, as Swedish ones are mostly mapped) is as good as
-- a footway for a run. A ferry is length the user does not run or ride, so it is a last resort.
INSERT INTO ref.activity_highway_factors (activity, highway, factor) VALUES
    ('running', 'footway', 1.0),
    ('running', 'path', 1.0),
    ('running', 'pedestrian', 1.0),
    ('running', 'track', 1.0),
    ('running', 'bridleway', 1.0),
    ('running', 'living_street', 1.0),
    ('running', 'cycleway', 1.0),
    ('running', 'residential', 1.2),
    ('running', 'steps', 1.2),
    ('running', 'service', 1.2),
    ('running', 'unclassified', 1.2),
    ('running', 'tertiary', 1.5),
    ('running', 'tertiary_link', 1.5),
    ('running', 'secondary', 2.0),
    ('running', 'secondary_link', 2.0),
    ('running', 'primary', 2.5),
    ('running', 'primary_link', 2.5),
    ('running', 'trunk', 3.0),
    ('running', 'trunk_link', 3.0),
    ('running', 'ferry', 5.0),
    ('cycling', 'cycleway', 1.0),
    ('cycling', 'living_street', 1.1),
    ('cycling', 'residential', 1.1),
    ('cycling', 'path', 1.2),
    ('cycling', 'track', 1.2),
    ('cycling', 'unclassified', 1.2),
    ('cycling', 'service', 1.3),
    ('cycling', 'tertiary', 1.3),
    ('cycling', 'tertiary_link', 1.3),
    ('cycling', 'secondary', 1.6),
    ('cycling', 'secondary_link', 1.6),
    ('cycling', 'primary', 2.0),
    ('cycling', 'primary_link', 2.0),
    ('cycling', 'trunk', 3.0),
    ('cycling', 'trunk_link', 3.0),
    ('cycling', 'ferry', 5.0);

INSERT INTO ref.attributes (key) VALUES
    ('green'), ('nature'), ('water'), ('quiet_streets'), ('sights'), ('bridges'), ('prepared'),
    ('hills');

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
    ('hills_bad', 'hills', -1, 'hills'),
    ('hills_good', 'hills', 1, 'hills'),
    ('lighting_bad', 'lighting', -1, NULL),
    ('lighting_good', 'lighting', 1, NULL),
    ('safety_bad', 'safety', -1, NULL),
    ('safety_good', 'safety', 1, NULL),
    ('crowding_bad', 'crowding', -1, NULL),
    ('access_bad', 'access', -1, NULL);
