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
GRANT INSERT ON enrich.pending_ways, enrich.pending_relations, enrich.pending_nodes,
    enrich.pending_elevation TO wayted_downloader;

-- wayted_mapper: reads ref and raw, builds graph.
GRANT USAGE ON SCHEMA ref, raw, graph TO wayted_mapper;
GRANT SELECT ON ALL TABLES IN SCHEMA ref, raw TO wayted_mapper;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA graph TO wayted_mapper;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA graph TO wayted_mapper;

-- wayted_enricher: reads ref, raw, way tags and segment reviews, builds enrich, writes only scores,
-- feedback and the edge queue in graph.
GRANT USAGE ON SCHEMA ref, raw, graph, enrich, app TO wayted_enricher;
GRANT SELECT ON ALL TABLES IN SCHEMA ref, raw TO wayted_enricher;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA enrich TO wayted_enricher;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA enrich TO wayted_enricher;
GRANT SELECT, UPDATE (scores, feedback, ascent_m, descent_m) ON graph.edges TO wayted_enricher;
-- Way tags, such as surface, bridge and tunnel, change how an edge is scored.
GRANT SELECT ON graph.ways TO wayted_enricher;
GRANT SELECT, INSERT, DELETE ON graph.pending_edges TO wayted_enricher;
GRANT USAGE ON SEQUENCE graph.pending_edges_id_seq TO wayted_enricher;
-- Only what counting needs: not the comments or where people went.
GRANT SELECT (id, user_id, activity, updated_at) ON app.segment_reviews TO wayted_enricher;
GRANT SELECT ON app.segment_review_edges, app.segment_review_reasons TO wayted_enricher;

-- wayted_api: reads ref and graph (including through pgRouting), owns the app data.
GRANT USAGE ON SCHEMA ref, graph, app TO wayted_api;
GRANT SELECT ON ALL TABLES IN SCHEMA ref, graph TO wayted_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA app TO wayted_api;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA app TO wayted_api;
-- The segment review triggers queue edges for the enricher as the API.
GRANT INSERT ON graph.pending_edges TO wayted_api;
GRANT USAGE ON SEQUENCE graph.pending_edges_id_seq TO wayted_api;

-- The route planner runs as the caller, so its view and functions read graph through the grants
-- above; pgRouting functions live in public and need nothing more.
GRANT USAGE ON SCHEMA routing TO wayted_api;
GRANT SELECT ON ALL TABLES IN SCHEMA routing TO wayted_api;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA routing TO wayted_api;

GRANT USAGE ON SCHEMA raw TO wayted_api;
GRANT SELECT ON raw.fetched_tiles TO wayted_api;
GRANT SELECT, INSERT, UPDATE ON raw.pending_tiles TO wayted_api;

-- For the dev API: the built features and what the enricher has left to do.
GRANT USAGE ON SCHEMA enrich TO wayted_api;
GRANT SELECT ON enrich.areas, enrich.lines, enrich.pending_ways, enrich.pending_relations,
    enrich.pending_nodes, enrich.pending_elevation TO wayted_api;
