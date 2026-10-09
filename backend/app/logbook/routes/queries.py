"""SQL queries for app.route and app.route_save.

Queries use psycopg-style ``%s`` placeholders. For geometry inputs, pass a
WKT LineString to CREATE_ROUTE / UPDATE_ROUTE_GEOMETRY. Coordinates in
ST_MakePoint are longitude first, then latitude.
"""

CREATE_ROUTE = """
INSERT INTO app.route (
    user_id,
    name,
    activity_id,
    route_type,
    distance_m,
    geom,
    is_public
)
VALUES (
    %s,
    %s,
    %s,
    %s::app.route_type,
    %s,
    ST_GeomFromText(%s, 4326),
    %s
)
RETURNING id, user_id, name, activity_id, route_type, distance_m,
          ST_AsText(geom) AS geom_wkt, is_public, created_at, updated_at;
"""

GET_ROUTE_BY_ID = """
SELECT id, user_id, name, activity_id, route_type, distance_m,
       ST_AsText(geom) AS geom_wkt, is_public, created_at, updated_at
FROM app.route
WHERE id = %s;
"""

GET_ACCESSIBLE_ROUTE_BY_ID = """
SELECT id, user_id, name, activity_id, route_type, distance_m,
       ST_AsText(geom) AS geom_wkt, is_public, created_at, updated_at
FROM app.route
WHERE id = %s
  AND (is_public = TRUE OR user_id = %s);
"""

LIST_USER_ROUTES = """
SELECT id, user_id, name, activity_id, route_type, distance_m,
       ST_AsText(geom) AS geom_wkt, is_public, created_at, updated_at
FROM app.route
WHERE user_id = %s
ORDER BY created_at DESC
LIMIT %s OFFSET %s;
"""

LIST_PUBLIC_ROUTES = """
SELECT id, user_id, name, activity_id, route_type, distance_m,
       ST_AsText(geom) AS geom_wkt, is_public, created_at, updated_at
FROM app.route
WHERE is_public = TRUE
ORDER BY created_at DESC
LIMIT %s OFFSET %s;
"""

LIST_PUBLIC_ROUTES_BY_ACTIVITY = """
SELECT id, user_id, name, activity_id, route_type, distance_m,
       ST_AsText(geom) AS geom_wkt, is_public, created_at, updated_at
FROM app.route
WHERE is_public = TRUE
  AND activity_id = %s
ORDER BY created_at DESC
LIMIT %s OFFSET %s;
"""

SEARCH_PUBLIC_ROUTES_NEAR_POINT = """
SELECT id, user_id, name, activity_id, route_type, distance_m,
       ST_AsText(geom) AS geom_wkt, is_public, created_at, updated_at
FROM app.route
WHERE is_public = TRUE
  AND ST_DWithin(
      geom::geography,
      ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
      %s
  )
ORDER BY ST_Distance(
    geom::geography,
    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
  )
LIMIT %s OFFSET %s;
"""

UPDATE_ROUTE = """
UPDATE app.route
SET name = %s,
    activity_id = %s,
    route_type = %s::app.route_type,
    distance_m = %s,
    is_public = %s,
    updated_at = NOW()
WHERE id = %s
  AND user_id = %s
RETURNING id, user_id, name, activity_id, route_type, distance_m,
          ST_AsText(geom) AS geom_wkt, is_public, created_at, updated_at;
"""

UPDATE_ROUTE_GEOMETRY = """
UPDATE app.route
SET geom = ST_GeomFromText(%s, 4326),
    distance_m = %s,
    updated_at = NOW()
WHERE id = %s
  AND user_id = %s
RETURNING id, ST_AsText(geom) AS geom_wkt, distance_m, updated_at;
"""

DELETE_ROUTE = """
DELETE FROM app.route
WHERE id = %s
  AND user_id = %s
RETURNING id;
"""

SAVE_ROUTE = """
INSERT INTO app.route_save (user_id, route_id)
VALUES (%s, %s)
ON CONFLICT (user_id, route_id) DO NOTHING
RETURNING user_id, route_id, created_at;
"""

UNSAVE_ROUTE = """
DELETE FROM app.route_save
WHERE user_id = %s
  AND route_id = %s
RETURNING user_id, route_id;
"""

LIST_SAVED_ROUTES = """
SELECT r.id, r.user_id, r.name, r.activity_id, r.route_type,
       r.distance_m, ST_AsText(r.geom) AS geom_wkt,
       r.is_public, r.created_at, r.updated_at,
       rs.created_at AS saved_at
FROM app.route_save AS rs
JOIN app.route AS r ON r.id = rs.route_id
WHERE rs.user_id = %s
ORDER BY rs.created_at DESC
LIMIT %s OFFSET %s;
"""

IS_ROUTE_SAVED = """
SELECT EXISTS (
    SELECT 1
    FROM app.route_save
    WHERE user_id = %s
      AND route_id = %s
) AS is_saved;
"""

COUNT_ROUTE_SAVES = """
SELECT COUNT(*) AS save_count
FROM app.route_save
WHERE route_id = %s;
"""
