"""SQL for route reviews. Every query is limited to the signed-in user's own rows."""

# The owner's review of route r as one JSON object, or NULL.
REVIEW_OF_ROUTE = """
    (SELECT jsonb_build_object(
                'answers', coalesce(
                    (SELECT jsonb_object_agg(a.attribute, a.answer)
                     FROM app.route_review_answers a
                     WHERE a.user_id = v.user_id AND a.route_id = v.route_id),
                    '{}'),
                'comment', v.comment,
                'created_at', v.created_at,
                'updated_at', v.updated_at)
     FROM app.route_reviews v
     WHERE v.route_id = r.id AND v.user_id = r.user_id)
"""

# Keeps the route from being deleted before the review is in.
OWNS_ROUTE = """
    SELECT 1 FROM app.routes WHERE id = %(route_id)s AND user_id = %(user_id)s FOR KEY SHARE
"""

GET_REVIEW = f"""
    SELECT {REVIEW_OF_ROUTE} FROM app.routes r
    WHERE r.id = %(route_id)s AND r.user_id = %(user_id)s
"""

UPSERT_REVIEW = """
    INSERT INTO app.route_reviews (user_id, route_id, comment)
    VALUES (%(user_id)s, %(route_id)s, %(comment)s)
    ON CONFLICT (user_id, route_id) DO UPDATE SET comment = EXCLUDED.comment, updated_at = now()
"""

GET_ANSWERS = """
    SELECT attribute, answer FROM app.route_review_answers
    WHERE user_id = %(user_id)s AND route_id = %(route_id)s
"""

DELETE_ANSWERS = """
    DELETE FROM app.route_review_answers WHERE user_id = %(user_id)s AND route_id = %(route_id)s
"""

INSERT_ANSWERS = """
    INSERT INTO app.route_review_answers (user_id, route_id, attribute, answer)
    SELECT %(user_id)s, %(route_id)s, attribute, answer
    FROM unnest(%(attributes)s::text[], %(answers)s::smallint[]) AS a (attribute, answer)
"""

GET_WEIGHTS = """
    SELECT attribute, weight FROM app.user_preferences
    WHERE user_id = %(user_id)s AND attribute = ANY (%(attributes)s)
"""

UPSERT_WEIGHTS = """
    INSERT INTO app.user_preferences (user_id, attribute, weight)
    SELECT %(user_id)s, attribute, weight
    FROM unnest(%(attributes)s::text[], %(weights)s::numeric[]) AS w (attribute, weight)
    ON CONFLICT (user_id, attribute) DO UPDATE SET weight = EXCLUDED.weight
"""

DELETE_WEIGHTS = """
    DELETE FROM app.user_preferences
    WHERE user_id = %(user_id)s AND attribute = ANY (%(attributes)s)
"""

DELETE_REVIEW = """
    DELETE FROM app.route_reviews
    WHERE user_id = %(user_id)s AND route_id = %(route_id)s
    RETURNING route_id
"""
