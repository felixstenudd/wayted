import dataclasses
import math
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import psycopg
import pytest
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from app.graph import map_pending
from app.sources.tiles import Tile

from ..enrichment.area_data import add_square, run
from ..graph.raw_data import ORIGIN_LAT, ORIGIN_LON, STEP, Conn, add_line, edge_ids
from ..logbook.app_data import add_segment_review, add_user

pytestmark = pytest.mark.db

type Pool = AsyncConnectionPool[Conn]
# graph.edges.feedback: {activity: {topic: {"up": n, "down": n}}}, or a user's own votes as
# routing.own_votes gives them: {edge id: {topic: 1 or -1}}
type Votes = dict[str, dict[str, Any]]

# Grid steps are about 57 m east-west and 111 m north-south.
A = (1, 0, 0)
B = (2, 10, 0)
STRAIGHT = 10  # A to B along y = 0, about 570 m
DETOUR = 11  # A to B by way of y = 2, about 1010 m; the park covers most of it
PARK_BOX = (-2, 1, 12, 4)


def point(x: float, y: float) -> str:
    return f"SRID=4326;POINT({ORIGIN_LON + x * STEP} {ORIGIN_LAT + y * STEP})"


async def two_paths(conn: Conn, mapper_pool: Pool, enricher_pool: Pool) -> None:
    """A short path from A to B, and a longer one through a park."""
    await add_line(conn, STRAIGHT, [A, B], {"highway": "path"})
    await add_line(conn, DETOUR, [A, (3, 0, 2), (4, 10, 2), B], {"highway": "path"})
    await add_square(conn, 101, 101, PARK_BOX, {"leisure": "park"})
    await run(mapper_pool, enricher_pool)


async def route_ways(conn: Conn, edges_sql: str, source: int, target: int) -> list[int]:
    """Way ids of the cheapest path pgRouting finds, in order."""
    cur = await conn.execute(
        """
        SELECT e.way_id FROM pgr_dijkstra(%s, %s, %s) d JOIN graph.edges e ON e.id = d.edge
        ORDER BY d.seq
        """,
        (edges_sql, source, target),
    )
    return [way_id for (way_id,) in await cur.fetchall()]


async def cost_sql(
    conn: Conn,
    activity: str,
    weights: Mapping[str, float],
    used: list[int] | None = None,
    area: str | None = None,
    own: Votes | None = None,
    others: bool = True,
) -> str:
    cur = await conn.execute(
        "SELECT routing.cost_sql(routing.make_profile(%s, %s, '{}', %s, %s), %s::geometry, %s)",
        (activity, Jsonb(weights), Jsonb(own or {}), others, area, used or []),
    )
    row = await cur.fetchone()
    assert row is not None
    return str(row[0])


async def edge_costs(conn: Conn, edges_sql: str) -> dict[int, tuple[float, float]]:
    """(cost, reverse_cost) by edge id, as pgRouting reads them."""
    cur = await conn.execute(f"SELECT id, cost, reverse_cost FROM ({edges_sql}) n")
    return {id_: (cost, reverse_cost) for id_, cost, reverse_cost in await cur.fetchall()}


async def test_activity_edges_follow_access_and_one_way_rules(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    await add_line(admin_conn, 10, [(1, 0, 0), (2, 1, 0)], {"highway": "footway"})
    await add_line(
        admin_conn, 11, [(2, 1, 0), (3, 2, 0)], {"highway": "residential", "oneway": "yes"}
    )
    await map_pending(mapper_pool.connection)

    async with api_pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT e.way_id, a.activity, a.forward, a.backward
            FROM routing.activity_edges a JOIN graph.edges e USING (id)
            ORDER BY e.way_id, a.activity
            """
        )
        rows = await cur.fetchall()

    # Cyclists may not use the footway at all, and follow the one-way street.
    assert rows == [
        (10, "running", True, True),
        (11, "cycling", True, False),
        (11, "running", True, True),
    ]


async def test_activity_edges_take_the_factor_of_their_highway_class(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    await add_line(admin_conn, 10, [(1, 0, 0), (2, 1, 0)], {"highway": "residential"})
    # Open to cyclists by its tag, though cycling has no factor for bridleways.
    await add_line(
        admin_conn, 11, [(2, 1, 0), (3, 2, 0)], {"highway": "bridleway", "bicycle": "yes"}
    )
    await map_pending(mapper_pool.connection)

    async with api_pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT e.way_id, a.activity, a.factor
            FROM routing.activity_edges a JOIN graph.edges e USING (id)
            ORDER BY e.way_id, a.activity
            """
        )
        rows = await cur.fetchall()

    assert rows == [
        (10, "cycling", 1.1),
        (10, "running", 1.2),
        (11, "cycling", 1.0),
        (11, "running", 1.0),
    ]


async def test_profile_scales_weights_and_drops_zeros(api_pool: Pool) -> None:
    async with api_pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT (p).activity, (p).weights, (p).settings = routing.defaults()
            FROM routing.make_profile('running', %s) p
            """,
            (Jsonb({"green": 1, "nature": -0.5, "water": 0}),),
        )
        row = await cur.fetchone()

    assert row is not None
    activity, weights, default_settings = row
    assert activity == "running"
    assert weights == pytest.approx({"green": 2 / 3, "nature": -1 / 3})
    assert default_settings


async def test_rides_pay_more_for_turns_unless_the_request_says_otherwise(api_pool: Pool) -> None:
    async with api_pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT routing.setting(routing.make_profile(a, '{}', s), 'turns', 'turn_m')
            FROM (VALUES ('running', '{}'::jsonb), ('cycling', '{}'),
                         ('cycling', '{"turns": {"turn_m": 30}}')) v(a, s)
            """
        )
        running, cycling, asked = [turn_m for (turn_m,) in await cur.fetchall()]

    assert cycling > running == 60
    assert asked == 30


async def test_profile_lays_settings_over_the_defaults(api_pool: Pool) -> None:
    async with api_pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT (p).settings -> 'turns', (p).settings -> 'loops' -> 'sizes',
                   (p).settings - 'turns' - 'loops' = routing.defaults() - 'turns' - 'loops'
            FROM routing.make_profile('running', '{}', %s) p
            """,
            (Jsonb({"turns": {"turn_m": 80}, "loops": {"sizes": [1]}}),),
        )
        row = await cur.fetchone()

    assert row is not None
    turns, sizes, others_unchanged = row
    assert turns == {"turn_m": 80, "free_deg": 30, "hairpin_deg": 120, "hairpin_m": 1000}
    assert sizes == [1]
    assert others_unchanged


@pytest.mark.parametrize(
    ("activity", "weights", "settings", "message"),
    [
        ("swimming", {}, {}, "unknown activity"),
        ("running", [], {}, "weights must be an object"),
        ("running", {"green": 1.5}, {}, "weights must be numbers"),
        ("running", {"green": "a lot"}, {}, "weights must be numbers"),
        ("running", {}, [], "settings must be an object"),
        ("running", {}, {"turn_m": 80}, "unknown setting: turn_m"),
        ("running", {}, {"turns": {"turn": 80}}, "unknown setting: turns.turn"),
        ("running", {}, {"turns": 80}, "turns must be an object"),
        ("running", {}, {"turns": {"turn_m": "80"}}, "turns.turn_m must be a number"),
        ("running", {}, {"loops": {"sizes": []}}, "loops.sizes must be a list of numbers"),
        ("running", {}, {"loops": {"sizes": 1}}, "loops.sizes must be a list of numbers"),
        ("running", {}, {"turns": {"turn_m": -1}}, "must not be negative"),
        ("running", {}, {"doubling": {"lobe": {"weight": -1}}}, "must not be negative"),
        ("running", {}, {"cost": {"alpha": 1}}, "cost.alpha"),
        ("running", {}, {"legs": {"reuse_penalty": 0.5}}, "legs.reuse_penalty"),
        ("running", {}, {"plan": {"tolerance": 1}}, "plan.tolerance"),
        ("running", {}, {"plan": {"snap_m": 0}}, "plan.snap_m"),
        ("running", {}, {"plan": {"attempts": 0}}, "plan.attempts"),
        ("running", {}, {"feedback": {"damping": 0}}, "feedback.damping"),
        ("running", {}, {"feedback": {"access": 0.5}}, "feedback.access"),
    ],
)
async def test_profile_rejects_bad_input(
    api_pool: Pool, activity: str, weights: object, settings: object, message: str
) -> None:
    async with api_pool.connection() as conn:
        with pytest.raises(psycopg.errors.InvalidParameterValue, match=message):
            await conn.execute(
                "SELECT routing.make_profile(%s, %s, %s)",
                (activity, Jsonb(weights), Jsonb(settings)),
            )


async def test_cost_weighs_length_by_class_preference_and_reuse(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    await add_line(admin_conn, STRAIGHT, [A, B], {"highway": "residential", "oneway": "yes"})
    await map_pending(mapper_pool.connection)
    await admin_conn.execute(
        "UPDATE graph.edges SET scores = %s", (Jsonb({"green": 0.5, "nature": 1}),)
    )
    edge = (await edge_ids(admin_conn))[(STRAIGHT, 1, 2, 1)]
    weights = {"green": 1, "nature": -1}

    async with api_pool.connection() as conn:
        fresh = await edge_costs(conn, await cost_sql(conn, "cycling", weights))
        reused = await edge_costs(conn, await cost_sql(conn, "cycling", weights, used=[edge]))
        cur = await conn.execute("SELECT length_m FROM graph.edges WHERE id = %s", (edge,))
        row = await cur.fetchone()

    assert row is not None
    # Weights scale to 0.5 each, so the preference is 0.5 * 0.5 - 0.5 * 1 = -0.25. Residential
    # costs 1.1 for cycling, and the one-way street cannot be ridden backwards.
    expected = row[0] * 1.1 * (1 + 0.7 * 0.25)
    assert fresh[edge] == pytest.approx((expected, -1))
    assert reused[edge] == pytest.approx((4 * expected, -1))


async def voted_edge(conn: Conn, mapper_pool: Pool, feedback: Votes) -> int:
    """The straight path, half green, with users' votes on it as the enricher counts them."""
    await add_line(conn, STRAIGHT, [A, B], {"highway": "path"})
    await map_pending(mapper_pool.connection)
    await conn.execute(
        "UPDATE graph.edges SET scores = %s, feedback = %s",
        (Jsonb({"green": 0.5}), Jsonb(feedback)),
    )
    return (await edge_ids(conn))[(STRAIGHT, 1, 2, 1)]


async def cost_ratio(
    conn: Conn,
    edge: int,
    activity: str,
    weights: Mapping[str, float],
    feedback: Votes | None = None,
    own: Votes | None = None,
    others: bool = True,
) -> float:
    """The edge's cost under weights, over its cost without weights or votes."""
    if feedback is not None:
        await conn.execute("UPDATE graph.edges SET feedback = %s", (Jsonb(feedback),))
    sql = await cost_sql(conn, activity, weights, own=own, others=others)
    cost = (await edge_costs(conn, sql))[edge][0]
    await conn.execute("UPDATE graph.edges SET scores = '{}', feedback = '{}'")
    plain = (await edge_costs(conn, await cost_sql(conn, activity, {})))[edge][0]
    await conn.execute("UPDATE graph.edges SET scores = %s", (Jsonb({"green": 0.5}),))
    return cost / plain


async def test_votes_count_only_for_a_wanted_topic_and_the_same_activity(
    admin_conn: Conn, mapper_pool: Pool
) -> None:
    feedback = {
        "running": {"green": {"up": 3, "down": 0}},
        "cycling": {"green": {"up": 0, "down": 9}},
    }
    edge = await voted_edge(admin_conn, mapper_pool, feedback)

    wanted = await cost_ratio(admin_conn, edge, "running", {"green": 1}, feedback)
    avoided = await cost_ratio(admin_conn, edge, "running", {"green": -1}, feedback)

    # 3 up, damped by 3, balance 0.5: green 0.5 plus half of that.
    assert wanted == pytest.approx(1 - 0.7 * (0.5 + 0.5 * 0.5))
    # Avoiding green, the score alone counts; the cyclists' votes never count for a run.
    assert avoided == pytest.approx(1 + 0.7 * 0.5)


async def test_access_and_safety_votes_cost_more_whatever_the_weights(
    admin_conn: Conn, mapper_pool: Pool
) -> None:
    feedback = {
        "running": {"access": {"up": 0, "down": 3}},
        "cycling": {"safety": {"up": 0, "down": 3}},
    }
    edge = await voted_edge(admin_conn, mapper_pool, feedback)

    run = await cost_ratio(admin_conn, edge, "running", {}, feedback)
    ride = await cost_ratio(admin_conn, edge, "cycling", {}, feedback)

    # Balances of -0.5: access 1 + 3 * 0.5 for runners only; safety 1 + 0.5 * 0.5 for both.
    assert run == pytest.approx(2.5 * 1.25)
    assert ride == pytest.approx(1.25)


async def test_good_votes_on_safety_only_cancel_and_lighting_and_crowding_count_nothing(
    admin_conn: Conn, mapper_pool: Pool
) -> None:
    feedback = {
        "running": {
            "safety": {"up": 6, "down": 0},
            "lighting": {"up": 0, "down": 6},
            "crowding": {"up": 0, "down": 6},
        }
    }
    edge = await voted_edge(admin_conn, mapper_pool, feedback)

    assert await cost_ratio(admin_conn, edge, "running", {}, feedback) == pytest.approx(1)


async def test_appeal_and_cost_lean_on_votes_alike(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    # Scores and votes high enough that the preference is held at 1.
    feedback = {"running": {"green": {"up": 10, "down": 0}, "water": {"up": 0, "down": 2}}}
    edge = await voted_edge(admin_conn, mapper_pool, feedback)
    await admin_conn.execute("UPDATE graph.edges SET scores = %s", (Jsonb({"green": 1}),))
    weights = {"green": 1, "water": 0.25}

    async with api_pool.connection() as conn:
        cost = (await edge_costs(conn, await cost_sql(conn, "running", weights)))[edge][0]
        plain = (await edge_costs(conn, await cost_sql(conn, "running", {})))[edge][0]
        cur = await conn.execute(
            """
            SELECT routing.preference(p, e.scores, e.feedback), routing.preference(p, e.scores),
                   (SELECT appeal FROM routing.vertex_stats(p, ARRAY[e.source]))
            FROM routing.make_profile('running', %s) p, graph.edges e
            WHERE e.id = %s
            """,
            (Jsonb(weights), edge),
        )
        row = await cur.fetchone()

    assert row is not None
    voted, measured, appeal = row
    assert voted == pytest.approx((1 - cost / plain) / 0.7)
    assert voted == pytest.approx(min(1, 0.8 + 0.5 * 0.8 * 10 / 13 - 0.5 * 0.2 * 2 / 5))
    assert measured == pytest.approx(0.8)
    assert appeal == pytest.approx(voted)


async def reviewer(conn: Conn) -> UUID:
    """A user with no reviews yet; app tables are not emptied between tests."""
    await conn.execute("TRUNCATE app.users CASCADE")
    return await add_user(conn)


async def test_own_votes_are_the_latest_per_edge_and_topic(
    admin_conn: Conn, api_pool: Pool
) -> None:
    user = await reviewer(admin_conn)
    other = await add_user(admin_conn, "other@example.com")
    then, later = datetime(2026, 5, 1, tzinfo=UTC), datetime(2026, 6, 1, tzinfo=UTC)
    await add_segment_review(admin_conn, user, None, [1], ["green_good"], updated_at=then)
    await add_segment_review(
        admin_conn, user, None, [1, 2], ["green_bad", "access_bad"], updated_at=later
    )
    # A ride: its hills say nothing about runs, but feeling unsafe is about the place.
    await add_segment_review(
        admin_conn, user, None, [3], ["hills_good", "safety_bad"], activity="cycling"
    )
    await add_segment_review(admin_conn, other, None, [4], ["green_good"])

    async with api_pool.connection() as conn:
        cur = await conn.execute(
            "SELECT routing.own_votes(%s, 'running'), routing.own_votes(NULL, 'running')", (user,)
        )
        row = await cur.fetchone()

    assert row == (
        {"1": {"green": -1, "access": -1}, "2": {"green": -1, "access": -1}, "3": {"safety": -1}},
        {},
    )


async def test_own_votes_stand_in_for_everyones(admin_conn: Conn, mapper_pool: Pool) -> None:
    feedback = {
        "running": {"green": {"up": 3, "down": 0}},
        "cycling": {"safety": {"up": 0, "down": 3}},
    }
    edge = await voted_edge(admin_conn, mapper_pool, feedback)
    own = {str(edge): {"green": -1, "access": -1}}

    everyones = await cost_ratio(admin_conn, edge, "running", {"green": 1}, feedback, own)
    own_only = await cost_ratio(admin_conn, edge, "running", {"green": 1}, feedback, own, False)

    # Green 0.5 less half of the own -1: no preference left. Access at its full 4 at once, and
    # everyone's safety votes at 1.25, which do not count when only the user's own do.
    assert everyones == pytest.approx(4 * 1.25)
    assert own_only == pytest.approx(4)


async def test_planned_route_keeps_off_a_stretch_the_user_could_not_get_through(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool, api_pool: Pool
) -> None:
    await two_paths(admin_conn, mapper_pool, enricher_pool)
    straight = (await edge_ids(admin_conn))[(STRAIGHT, 1, 2, 1)]
    user = await reviewer(admin_conn)
    await add_segment_review(admin_conn, user, None, [straight], ["access_bad"])

    async def ways(user_id: UUID | None) -> list[int]:
        async with api_pool.connection() as conn:
            cur = await conn.execute(
                """
                SELECT DISTINCT e.way_id
                FROM jsonb_array_elements(
                         routing.plan_route('running', %s, %s, NULL, '{}', '{}', '[]', %s)
                         -> 'edges'
                     ) r
                JOIN graph.edges e ON e.id = (r ->> 'edge_id')::bigint
                """,
                (point(0, 0), point(10, 0), user_id),
            )
            return [way_id for (way_id,) in await cur.fetchall()]

    assert await ways(None) == [STRAIGHT]
    assert await ways(user) == [DETOUR]


async def test_length_is_plain_metres(admin_conn: Conn, mapper_pool: Pool, api_pool: Pool) -> None:
    await add_line(admin_conn, STRAIGHT, [A, B], {"highway": "primary"})
    await map_pending(mapper_pool.connection)
    edge = (await edge_ids(admin_conn))[(STRAIGHT, 1, 2, 1)]

    async with api_pool.connection() as conn:
        cur = await conn.execute("SELECT routing.length_sql('running', NULL)")
        row = await cur.fetchone()
        assert row is not None
        costs = await edge_costs(conn, row[0])
        cur = await conn.execute("SELECT length_m FROM graph.edges WHERE id = %s", (edge,))
        length = await cur.fetchone()

    assert length is not None
    assert costs[edge] == pytest.approx((length[0], length[0]))


async def test_route_takes_the_park_when_green_is_preferred(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool, api_pool: Pool
) -> None:
    await two_paths(admin_conn, mapper_pool, enricher_pool)

    async with api_pool.connection() as conn:
        indifferent = await route_ways(conn, await cost_sql(conn, "running", {}), 1, 2)
        green = await route_ways(conn, await cost_sql(conn, "running", {"green": 1}), 1, 2)

    assert indifferent == [STRAIGHT]
    assert green == [DETOUR]


async def test_a_run_takes_the_shared_path_beside_the_street(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    street, shared = 20, 21
    start, end = (51, 0, 0), (52, 40, 0)
    # About 2.3 km of street, and a shared foot and cycle path one row beside it, as Swedish paths
    # are mapped: about 6 % longer.
    await add_line(admin_conn, street, [start, end], {"highway": "residential"})
    await add_line(
        admin_conn,
        shared,
        [start, (53, 1, 1), (54, 39, 1), end],
        {"highway": "cycleway", "foot": "designated"},
    )
    await map_pending(mapper_pool.connection)

    async with api_pool.connection() as conn:
        ways = await route_ways(conn, await cost_sql(conn, "running", {}), 51, 52)

    assert set(ways) == {shared}


async def test_busier_roads_cost_a_run_more(api_pool: Pool) -> None:
    async with api_pool.connection() as conn:
        cur = await conn.execute(
            "SELECT highway, factor FROM ref.activity_highway_factors WHERE activity = 'running'"
        )
        factor: dict[str, float] = dict(await cur.fetchall())

    assert factor["cycleway"] == factor["footway"]
    busier = ["footway", "residential", "tertiary", "secondary", "primary", "trunk"]
    assert [factor[h] for h in busier] == sorted(factor[h] for h in busier)
    assert len({factor[h] for h in busier}) == len(busier)


async def test_planned_route_without_a_target_takes_the_park_when_green_is_preferred(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool, api_pool: Pool
) -> None:
    await two_paths(admin_conn, mapper_pool, enricher_pool)

    async def ways(weights: dict[str, float]) -> list[int]:
        async with api_pool.connection() as conn:
            cur = await conn.execute(
                """
                SELECT e.way_id
                FROM jsonb_array_elements(
                         routing.plan_route('running', %s, %s, NULL, %s) -> 'edges'
                     ) WITH ORDINALITY AS r(step, n)
                JOIN graph.edges e ON e.id = (r.step ->> 'edge_id')::bigint
                ORDER BY r.n
                """,
                (point(0, 0), point(10, 0), Jsonb(weights)),
            )
            return [way_id for (way_id,) in await cur.fetchall()]

    assert await ways({}) == [STRAIGHT]
    assert await ways({"green": 1}) == [DETOUR]


async def test_planned_route_takes_the_hills_only_when_they_are_preferred(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool, api_pool: Pool
) -> None:
    # A ridge under the detour, rising 15 % to its middle and falling again, so steep that the
    # detour scores as hilly as it gets, and level ground under the straight path and the
    # detour's ends. Cells are 0.0002 by 0.0001 degrees from
    # 17.995 east and 59.304 north, so the detour (y = 2) is row 20 and the straight path row 40.
    column_m = 0.0002 * 111_320 * math.cos(math.radians(ORIGIN_LAT))
    await admin_conn.execute(
        """
        INSERT INTO raw.elevation_tiles (z, x, y, rast)
        SELECT %(z)s, %(x)s, %(y)s, ST_MapAlgebra(
            ST_AddBand(
                ST_MakeEmptyRaster(100, 60, 17.995, 59.304, 0.0002, -0.0001, 0, 0, 4326),
                '32BF'::text, 0, -32767
            ),
            1, '32BF', %(heights)s
        )
        """,
        {
            **dataclasses.asdict(Tile.from_lat_lon(ORIGIN_LAT, ORIGIN_LON, 14)),
            "heights": "10 + CASE WHEN [rast.y] < 30 "
            f"THEN greatest(0, 25 - abs([rast.x] - 50)) * {0.15 * column_m} ELSE 0 END",
        },
    )
    await two_paths(admin_conn, mapper_pool, enricher_pool)

    async def planned(weights: dict[str, float]) -> tuple[list[int], dict[str, Any]]:
        async with api_pool.connection() as conn:
            cur = await conn.execute(
                "SELECT routing.plan_route('running', %s, %s, NULL, %s)",
                (point(0, 0), point(10, 0), Jsonb(weights)),
            )
            row = await cur.fetchone()
            assert row is not None
            route = row[0]
            cur = await conn.execute(
                "SELECT DISTINCT way_id FROM graph.edges WHERE id = ANY(%s)",
                ([step["edge_id"] for step in route["edges"]],),
            )
            return [way_id for (way_id,) in await cur.fetchall()], route

    indifferent, flat = await planned({})
    avoided, _ = await planned({"hills": -1})
    preferred, hilly = await planned({"hills": 1})

    assert indifferent == avoided == [STRAIGHT]
    assert preferred == [DETOUR]
    assert flat["scores"]["hills"]["mean"] == pytest.approx(0, abs=0.05)
    assert hilly["scores"]["hills"]["mean"] > 0.5
    assert (flat["ascent_m"], flat["descent_m"]) == (0, 0)
    # Up the ridge and down again: 25 columns rising 15 % each way, less what smoothing rounds off.
    assert hilly["ascent_m"] == pytest.approx(25 * 0.15 * column_m, rel=0.15)
    assert hilly["descent_m"] == pytest.approx(hilly["ascent_m"], rel=0.05)


async def test_route_climb_follows_the_direction_of_travel_and_needs_heights(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool, api_pool: Pool
) -> None:
    await two_paths(admin_conn, mapper_pool, enricher_pool)
    edges = await edge_ids(admin_conn)
    straight = edges[(STRAIGHT, 1, 2, 1)]
    detour = [edges[key] for key in sorted(edges) if key[0] == DETOUR]
    await admin_conn.execute(
        "UPDATE graph.edges SET ascent_m = 12, descent_m = 3 WHERE id = %s", (straight,)
    )

    async def climb(edge_ids: list[int], forward: list[bool]) -> tuple[Any, Any]:
        async with api_pool.connection() as conn:
            cur = await conn.execute("SELECT routing.route_climb(%s, %s)", (edge_ids, forward))
            row = await cur.fetchone()
            assert row is not None
            return row[0]["ascent_m"], row[0]["descent_m"]

    assert await climb([straight], [True]) == (12, 3)
    assert await climb([straight, straight], [True, False]) == (15, 15)
    # The detour, with no heights, is most of the length.
    assert await climb([straight, *detour], [True] * (1 + len(detour))) == (None, None)


async def test_route_avoids_edges_it_already_used(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool, api_pool: Pool
) -> None:
    await two_paths(admin_conn, mapper_pool, enricher_pool)
    straight = (await edge_ids(admin_conn))[(STRAIGHT, 1, 2, 1)]

    async with api_pool.connection() as conn:
        sql = await cost_sql(conn, "running", {}, used=[straight])
        ways = await route_ways(conn, sql, 2, 1)

    assert ways == [DETOUR]


async def test_route_keeps_to_the_area(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool, api_pool: Pool
) -> None:
    await two_paths(admin_conn, mapper_pool, enricher_pool)
    # Leaves out the straight path, which runs along y = 0.
    area = (
        f"SRID=4326;POLYGON(({ORIGIN_LON - STEP} {ORIGIN_LAT + 0.5 * STEP}, "
        f"{ORIGIN_LON + 11 * STEP} {ORIGIN_LAT + 0.5 * STEP}, "
        f"{ORIGIN_LON + 11 * STEP} {ORIGIN_LAT + 3 * STEP}, "
        f"{ORIGIN_LON - STEP} {ORIGIN_LAT + 3 * STEP}, "
        f"{ORIGIN_LON - STEP} {ORIGIN_LAT + 0.5 * STEP}))"
    )

    async with api_pool.connection() as conn:
        ways = await route_ways(conn, await cost_sql(conn, "running", {}, area=area), 1, 2)

    assert ways == [DETOUR]


async def test_near_vertices_are_those_the_activity_can_use(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    await add_line(admin_conn, 10, [(1, 0, 0), (2, 2, 0)], {"highway": "footway"})
    await add_line(admin_conn, 11, [(3, 0, 1), (4, 2, 1)], {"highway": "residential"})
    await map_pending(mapper_pool.connection)
    near_footway = point(0.2, 0.1)

    async with api_pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT (SELECT array_agg(vertex ORDER BY distance_m)
                    FROM routing.near_vertices(a.activity, %(p)s, a.max_m))
            FROM (VALUES ('running', 100), ('cycling', 200), ('cycling', 50)) a(activity, max_m)
            """,
            {"p": near_footway},
        )
        rows = await cur.fetchall()

    # Cyclists may not use the footway, so only the street is near, unless it is too far.
    assert rows == [([1],), ([3, 4],), (None,)]


async def isolated_footway_beside_a_street(conn: Conn, mapper_pool: Pool) -> None:
    """A footway joined to nothing, 111 m north of a 570 m street that starts below it."""
    await add_line(conn, 10, [(1, 0, 1), (2, 2, 1)], {"highway": "footway"})
    await add_line(conn, 11, [(3, 0, 0), (4, 10, 0)], {"highway": "residential"})
    await map_pending(mapper_pool.connection)


async def snap_points(pool: Pool, points: list[str], min_network_m: float) -> list[int] | None:
    async with pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT routing.snap_points(
                       routing.make_profile('running'), NULL,
                       ARRAY(SELECT p::geometry FROM unnest(%s::text[]) p), %s, %s
                   )
            """,
            (points, ["start", "finish"][: len(points)], min_network_m),
        )
        row = await cur.fetchone()
    assert row is not None
    snapped: list[int] | None = row[0]
    return snapped


async def test_route_ends_snap_to_roads_that_join(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    await isolated_footway_beside_a_street(admin_conn, mapper_pool)
    # 44 m from the footway, 67 m from the street; the finish is by the street's far end.
    start, finish = point(0, 0.6), point(10, 0.1)

    assert await snap_points(api_pool, [start, finish], 0) == [3, 4]


async def test_loop_start_snaps_to_a_network_long_enough(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    await isolated_footway_beside_a_street(admin_conn, mapper_pool)
    start = point(0, 0.6)

    assert await snap_points(api_pool, [start], 0) == [1]
    # The footway is 114 m long.
    assert await snap_points(api_pool, [start], 200) == [3]
    assert await snap_points(api_pool, [start], 1_000) is None


@pytest.mark.parametrize(("points", "message"), [((40, 0), "start"), ((0, 40), "finish")])
async def test_point_far_from_any_road_cannot_be_snapped(
    admin_conn: Conn,
    mapper_pool: Pool,
    api_pool: Pool,
    points: tuple[float, float],
    message: str,
) -> None:
    await isolated_footway_beside_a_street(admin_conn, mapper_pool)

    with pytest.raises(psycopg.errors.NoDataFound, match=f"no road near the {message}"):
        await snap_points(api_pool, [point(points[0], 0), point(points[1], 0)], 0)


async def test_only_the_api_may_plan_routes(mapper_pool: Pool, api_pool: Pool) -> None:
    async with api_pool.connection() as conn:
        await conn.execute("SELECT routing.make_profile('running')")
    async with mapper_pool.connection() as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            await conn.execute("SELECT routing.make_profile('running')")
