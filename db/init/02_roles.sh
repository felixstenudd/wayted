#!/usr/bin/env bash
# A .sh script instead of .sql because role passwords come from the environment.
# The roles own nothing; their permissions are granted in 80_grants.sql.
set -euo pipefail

psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v downloader_password="$WAYTED_DOWNLOADER_PASSWORD" \
  -v mapper_password="$WAYTED_MAPPER_PASSWORD" \
  -v enricher_password="$WAYTED_ENRICHER_PASSWORD" \
  -v api_password="$WAYTED_API_PASSWORD" <<'SQL'
CREATE ROLE wayted_downloader LOGIN PASSWORD :'downloader_password';
CREATE ROLE wayted_mapper LOGIN PASSWORD :'mapper_password';
CREATE ROLE wayted_enricher LOGIN PASSWORD :'enricher_password';
CREATE ROLE wayted_api LOGIN PASSWORD :'api_password';
SQL
