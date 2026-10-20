"""SQL for the signed-in user's default weights."""

# Everything that writes a user's weights takes this first, so a route review's nudge and a save
# of the defaults never interleave. Row locks on the weights alone would miss weights not stored
# yet. NO KEY UPDATE leaves inserts that reference the user free.
LOCK_WEIGHTS = "SELECT 1 FROM app.users WHERE id = %(user_id)s FOR NO KEY UPDATE"

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
