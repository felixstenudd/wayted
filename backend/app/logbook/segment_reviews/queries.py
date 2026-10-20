"""SQL for segment reviews. Every query is limited to the signed-in user's own rows."""

LIST_REASONS = """
    SELECT code, topic, sentiment, attribute FROM ref.review_reasons
    ORDER BY attribute IS NULL, topic, sentiment DESC
"""

REASON_TOPICS = "SELECT code, topic FROM ref.review_reasons WHERE code = ANY (%(reasons)s)"

ROUTE_EDGE_COUNT = """
    SELECT (SELECT count(*) FROM app.route_edges e WHERE e.route_id = r.id)
    FROM app.routes r
    WHERE r.id = %(route_id)s AND r.user_id = %(user_id)s
"""

# The stretch is cut from the route's own line: from where edge from_seq starts (the end of the
# edge before it) to where edge to_seq ends.
CREATE_REVIEW = """
    WITH ends AS (
        SELECT coalesce(
                   (SELECT last_point FROM app.route_edges
                    WHERE route_id = %(route_id)s AND seq = %(from_seq)s - 1),
                   0) AS first_point,
               (SELECT last_point FROM app.route_edges
                WHERE route_id = %(route_id)s AND seq = %(to_seq)s) AS last_point
    )
    INSERT INTO app.segment_reviews (user_id, route_id, activity, from_seq, to_seq, geom, comment)
    SELECT r.user_id, r.id, r.activity, %(from_seq)s, %(to_seq)s,
           ST_MakeLine(ARRAY(
               SELECT p.geom FROM ST_DumpPoints(r.geom) p
               WHERE p.path[1] - 1 BETWEEN ends.first_point AND ends.last_point
               ORDER BY p.path[1]
           )),
           %(comment)s
    FROM app.routes r, ends
    WHERE r.id = %(route_id)s
    RETURNING id
"""

ADD_EDGES = """
    INSERT INTO app.segment_review_edges (review_id, edge_id)
    SELECT DISTINCT %(review_id)s, edge_id FROM app.route_edges
    WHERE route_id = %(route_id)s AND seq BETWEEN %(from_seq)s AND %(to_seq)s
"""

ADD_REASONS = """
    INSERT INTO app.segment_review_reasons (review_id, reason)
    SELECT %(review_id)s, unnest(%(reasons)s::text[])
"""

DELETE_REASONS = "DELETE FROM app.segment_review_reasons WHERE review_id = %(review_id)s"

_REVIEW = """
    s.id, s.route_id, s.from_seq, s.to_seq, s.activity,
    ST_AsGeoJSON(s.geom, 6)::jsonb AS geometry,
    ARRAY(SELECT x.reason FROM app.segment_review_reasons x
          WHERE x.review_id = s.id ORDER BY x.reason) AS reasons,
    s.comment, s.created_at, s.updated_at
"""

GET_REVIEW = f"""
    SELECT {_REVIEW} FROM app.segment_reviews s
    WHERE s.id = %(review_id)s AND s.user_id = %(user_id)s
"""

LIST_REVIEWS = f"""
    SELECT {_REVIEW} FROM app.segment_reviews s
    WHERE s.route_id = %(route_id)s AND s.user_id = %(user_id)s
    ORDER BY s.from_seq, s.created_at
"""

# updated_at decides which of a user's reviews is the latest on a topic.
CHANGE_REVIEW = """
    UPDATE app.segment_reviews SET comment = %(comment)s, updated_at = now()
    WHERE id = %(review_id)s AND user_id = %(user_id)s
    RETURNING id
"""

DELETE_REVIEW = """
    DELETE FROM app.segment_reviews WHERE id = %(review_id)s AND user_id = %(user_id)s
    RETURNING id
"""
