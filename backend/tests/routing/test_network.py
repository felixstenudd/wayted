from collections.abc import Mapping

import psycopg
import pytest
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from app.graph import map_pending

from ..enrichment.area_data import add_square, run
from ..graph.raw_data import ORIGIN_LAT, ORIGIN_LON, STEP, Conn, add_line, edge_ids

pytestmark = pytest.mark.db

type Pool = AsyncConnectionPool[Conn]

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
) -> str:
    cur = await conn.execute(
        "SELECT routing.cost_sql(routing.make_profile(%s, %s), %s::geometry, %s)",
        (activity, Jsonb(weights), area, used or []),
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
        (10, "running", 1.1),
        (11, "cycling", 1.0),
        (11, "running", 1.0),
    ]


async def test_profile_scales_weights_and_drops_zeros(api_pool: Pool) -> None:
    async with api_pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT (p).activity, (p).weights, (p).settings = routing.defaults()
            FROM routing.make_profile('cycling', %s) p
            """,
            (Jsonb({"green": 1, "nature": -0.5, "water": 0}),),
        )
        row = await cur.fetchone()

    assert row is not None
    activity, weights, default_settings = row
    assert activity == "cycling"
    assert weights == pytest.approx({"green": 2 / 3, "nature": -1 / 3})
    assert default_settings


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


async def test_snap_finds_the_nearest_vertex_the_activity_can_use(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    await add_line(admin_conn, 10, [(1, 0, 0), (2, 2, 0)], {"highway": "footway"})
    await add_line(admin_conn, 11, [(3, 0, 1), (4, 2, 1)], {"highway": "residential"})
    await map_pending(mapper_pool.connection)
    near_footway = point(0.2, 0.1)

    async with api_pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT routing.snap('running', %(p)s, 100),
                   routing.snap('cycling', %(p)s, 200),
                   routing.snap('cycling', %(p)s, 50)
            """,
            {"p": near_footway},
        )
        row = await cur.fetchone()

    # Cyclists may not use the footway, so they snap to the street, unless it is too far.
    assert row == (1, 3, None)


async def test_only_the_api_may_plan_routes(mapper_pool: Pool, api_pool: Pool) -> None:
    async with api_pool.connection() as conn:
        await conn.execute("SELECT routing.make_profile('running')")
    async with mapper_pool.connection() as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            await conn.execute("SELECT routing.make_profile('running')")
