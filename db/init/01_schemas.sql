-- ref:   lookup data shared by everything (attributes, activities).
-- raw:   data as downloaded from OSM and other sources, before mapping.
-- graph: the routable network built from raw by the mapper.
-- enrich: feature geometry built from raw by the enricher, to score graph edges.
-- app:   user-owned data written through the API (users, routes, feedback).
CREATE SCHEMA ref;
CREATE SCHEMA raw;
CREATE SCHEMA graph;
CREATE SCHEMA enrich;
CREATE SCHEMA app;
