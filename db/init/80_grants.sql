-- Every permission in one place. Runs after all tables exist, so "ALL TABLES"
-- covers them; a schema change means a volume reset, which reruns this file.

-- wayted_downloader: fills raw, reading which layers to fetch from ref.
GRANT USAGE ON SCHEMA ref, raw TO wayted_downloader;
GRANT SELECT ON ref.source_layers TO wayted_downloader;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA raw TO wayted_downloader;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA raw TO wayted_downloader;
-- The triggers on raw queue changes for the mapper and the enricher as the downloader.
GRANT USAGE ON SCHEMA graph, enrich TO wayted_downloader;
GRANT INSERT ON graph.pending_ways, graph.pending_nodes TO wayted_downloader;
GRANT INSERT ON enrich.pending_ways, enrich.pending_relations, enrich.pending_nodes
    TO wayted_downloader;

-- wayted_mapper: reads ref and raw, builds graph.
GRANT USAGE ON SCHEMA ref, raw, graph TO wayted_mapper;
GRANT SELECT ON ALL TABLES IN SCHEMA ref, raw TO wayted_mapper;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA graph TO wayted_mapper;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA graph TO wayted_mapper;

-- wayted_enricher: reads ref, raw and way tags, builds enrich, writes only scores and the edge
-- queue in graph.
GRANT USAGE ON SCHEMA ref, raw, graph, enrich TO wayted_enricher;
GRANT SELECT ON ALL TABLES IN SCHEMA ref, raw TO wayted_enricher;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA enrich TO wayted_enricher;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA enrich TO wayted_enricher;
GRANT SELECT, UPDATE (scores) ON graph.edges TO wayted_enricher;
GRANT SELECT ON graph.ways TO wayted_enricher;
GRANT SELECT, INSERT, DELETE ON graph.pending_edges TO wayted_enricher;
GRANT USAGE ON SEQUENCE graph.pending_edges_id_seq TO wayted_enricher;

-- wayted_api: reads ref and graph (including through pgRouting), owns the app data.
GRANT USAGE ON SCHEMA ref, graph, app TO wayted_api;
GRANT SELECT ON ALL TABLES IN SCHEMA ref, graph TO wayted_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA app TO wayted_api;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA app TO wayted_api;

GRANT USAGE ON SCHEMA raw TO wayted_api;
GRANT SELECT ON raw.fetched_tiles TO wayted_api;
GRANT SELECT, INSERT, UPDATE ON raw.pending_tiles TO wayted_api;

-- For the dev API: the built features and what the enricher has left to do.
GRANT USAGE ON SCHEMA enrich TO wayted_api;
GRANT SELECT ON enrich.areas, enrich.lines, enrich.pending_ways, enrich.pending_relations, enrich.pending_nodes
    TO wayted_api;
