UPSERT_ROUTE_REVIEW = """
INSERT INTO app.route_review (user_id, route_id, rating, comment)
VALUES (%s, %s, %s, %s)
ON CONFLICT (user_id, route_id)
DO UPDATE SET
    rating = EXCLUDED.rating,
    comment = EXCLUDED.comment,
    updated_at = NOW()
RETURNING user_id, route_id, rating, comment, created_at, updated_at;
"""

GET_USER_ROUTE_REVIEW = """
SELECT user_id, route_id, rating, comment, created_at, updated_at
FROM app.route_review
WHERE user_id = %s
  AND route_id = %s;
"""

LIST_ROUTE_REVIEWS = """
SELECT user_id, route_id, rating, comment, created_at, updated_at
FROM app.route_review
WHERE route_id = %s
ORDER BY created_at DESC
LIMIT %s OFFSET %s;
"""

UPDATE_ROUTE_REVIEW = """
UPDATE app.route_review
SET rating = %s,
    comment = %s,
    updated_at = NOW()
WHERE user_id = %s
  AND route_id = %s
RETURNING user_id, route_id, rating, comment, created_at, updated_at;
"""

DELETE_ROUTE_REVIEW = """
DELETE FROM app.route_review
WHERE user_id = %s
  AND route_id = %s
RETURNING user_id, route_id;
"""

GET_ROUTE_REVIEW_SUMMARY = """
SELECT AVG(rating)::double precision AS average_rating,
       COUNT(*) AS review_count
FROM app.route_review
WHERE route_id = %s;
"""

UPSERT_SEGMENT_RATING = """
INSERT INTO app.segment_rating (user_id, segment_id, rating)
VALUES (%s, %s, %s)
ON CONFLICT (user_id, segment_id)
DO UPDATE SET
    rating = EXCLUDED.rating,
    updated_at = NOW()
RETURNING user_id, segment_id, rating, created_at, updated_at;
"""

GET_USER_SEGMENT_RATING = """
SELECT user_id, segment_id, rating, created_at, updated_at
FROM app.segment_rating
WHERE user_id = %s
  AND segment_id = %s;
"""

LIST_USER_SEGMENT_RATINGS = """
SELECT user_id, segment_id, rating, created_at, updated_at
FROM app.segment_rating
WHERE user_id = %s
ORDER BY updated_at DESC
LIMIT %s OFFSET %s;
"""

GET_SEGMENT_RATING_SUMMARY = """
SELECT AVG(rating)::double precision AS average_rating,
       COUNT(*) AS rating_count
FROM app.segment_rating
WHERE segment_id = %s;
"""

DELETE_SEGMENT_RATING = """
DELETE FROM app.segment_rating
WHERE user_id = %s
  AND segment_id = %s
RETURNING user_id, segment_id;
"""
