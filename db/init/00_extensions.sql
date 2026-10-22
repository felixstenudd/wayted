CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgrouting;
-- Terrain heights are a grid of cells (raw.elevation_tiles).
CREATE EXTENSION IF NOT EXISTS postgis_raster;

-- GDAL reads no file format until allowed; the elevation downloader stores GeoTIFFs. Set for the
-- server, as only a superuser may set it and the roles that read rasters are not.
ALTER SYSTEM SET postgis.gdal_enabled_drivers = 'GTiff';
SELECT pg_reload_conf();
