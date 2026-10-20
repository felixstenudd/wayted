"""SQL for the signed-in user's default weights."""

GET_WEIGHTS = """
    SELECT attribute, weight FROM app.user_preferences WHERE user_id = %(user_id)s
"""

DELETE_WEIGHTS = "DELETE FROM app.user_preferences WHERE user_id = %(user_id)s"

INSERT_WEIGHTS = """
    INSERT INTO app.user_preferences (user_id, attribute, weight)
    SELECT %(user_id)s, attribute, weight
    FROM unnest(%(attributes)s::text[], %(weights)s::numeric[]) AS w (attribute, weight)
    WHERE round(weight, 2) <> 0
"""
