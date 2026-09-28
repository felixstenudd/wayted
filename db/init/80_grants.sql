-- Every permission in one place. Runs after all tables exist, so "ALL TABLES"
-- covers them; a schema change means a volume reset, which reruns this file.

-- wayted_downloader: fills raw, reading which layers to fetch from ref.
GRANT USAGE ON SCHEMA ref, raw TO wayted_downloader;
GRANT SELECT ON ref.source_layers TO wayted_downloader;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA raw TO wayted_downloader;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA raw TO wayted_downloader;

-- wayted_mapper: reads ref and raw, builds graph.
GRANT USAGE ON SCHEMA ref, raw, graph TO wayted_mapper;
GRANT SELECT ON ALL TABLES IN SCHEMA ref, raw TO wayted_mapper;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA graph TO wayted_mapper;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA graph TO wayted_mapper;

-- wayted_api: reads ref and graph (including through pgRouting), owns the app data.
GRANT USAGE ON SCHEMA ref, graph, app TO wayted_api;
GRANT SELECT ON ALL TABLES IN SCHEMA ref, graph TO wayted_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA app TO wayted_api;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA app TO wayted_api;
