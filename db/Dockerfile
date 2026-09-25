# The official postgres image is multi-arch; the pgrouting/* images only ship amd64.
FROM postgres:17-bookworm

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      postgresql-17-postgis-3 \
      postgresql-17-pgrouting \
 && rm -rf /var/lib/apt/lists/*

COPY init/ /docker-entrypoint-initdb.d/
