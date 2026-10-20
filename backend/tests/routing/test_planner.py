import math
from typing import Any

import psycopg
import pytest
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from app.graph import map_pending

from ..enrichment.area_data import add_square, run
from ..graph.raw_data import ORIGIN_LAT, ORIGIN_LON, STEP, Conn, add_line
from .network_data import COLUMN_STEPS, add_grid, grid_point, node_id

pytestmark = pytest.mark.db

type Pool = AsyncConnectionPool[Conn]

STREET = {"highway": "residential"}
CENTRE = grid_point(12, 12)
EAST = grid_point(20, 12)
TOLERANCE = 0.07


async def plan(
    pool: Pool,
    activity: str,
    start: str,
    finish: str | None,
    target_m: float,
    weights: dict[str, float] | None = None,
    options: dict[str, float] | None = None,
) -> dict[str, Any]:
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT routing.plan_route(%s, %s, %s, %s, %s, %s)",
            (activity, start, finish, target_m, Jsonb(weights or {}), Jsonb(options or {})),
        )
        row = await cur.fetchone()
    assert row is not None
    route: dict[str, Any] = row[0]
    return route


def ends(route: dict[str, Any]) -> tuple[list[float], list[float]]:
    coordinates = route["geometry"]["coordinates"]
    return coordinates[0], coordinates[-1]


def coordinates(column: int, row: int) -> object:
    """A grid crossing as GeoJSON coordinates, to compare with approximately."""
    return pytest.approx([ORIGIN_LON + column * COLUMN_STEPS * STEP, ORIGIN_LAT + row * STEP])


async def grid(conn: Conn, mapper_pool: Pool, one_way_rows: frozenset[int] = frozenset()) -> None:
    await add_grid(conn, STREET, one_way_rows)
    await map_pending(mapper_pool.connection)


async def route_ways(
    pool: Pool, vias: list[int], weights: dict[str, float] | None = None, turn_m: float = 60
) -> list[int]:
    """Way ids of routing.route_edges through vias, one per edge, in travel order."""
    async with pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT e.way_id
            FROM routing.route_edges(
                     routing.make_profile('running', %s, p_turn_m => %s), NULL, %s::bigint[]
                 ) r
            JOIN graph.edges e ON e.id = r.edge_id
            ORDER BY r.step
            """,
            (Jsonb(weights or {}), turn_m, vias),
        )
        return [way_id for (way_id,) in await cur.fetchall()]


def turns(ways: list[int]) -> int:
    """How often a route on the grid changes street, which is a turn there."""
    return sum(a != b for a, b in zip(ways, ways[1:], strict=False))


@pytest.mark.parametrize("target_m", [2_000, 4_000, 6_000])
async def test_loop_returns_to_its_start_at_about_the_target(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool, target_m: int
) -> None:
    await grid(admin_conn, mapper_pool)

    route = await plan(api_pool, "running", CENTRE, None, target_m)

    assert route["length_m"] == pytest.approx(target_m, rel=TOLERANCE)
    assert route["warnings"] == []
    assert ends(route) == (coordinates(12, 12), coordinates(12, 12))
    # A grid has streets enough that the loop never has to go back the way it came.
    assert route["reused_m"] < 0.05 * route["length_m"]


async def test_route_line_is_continuous_and_matches_its_edges(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    await grid(admin_conn, mapper_pool)

    route = await plan(api_pool, "running", CENTRE, None, 3_000)

    async with api_pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT ST_Length(ST_GeomFromGeoJSON(%s)::geography),
                   (SELECT sum(length_m) FROM graph.edges e, jsonb_array_elements_text(%s) i
                    WHERE e.id = i::bigint)
            """,
            (Jsonb(route["geometry"]), Jsonb(route["edges"])),
        )
        row = await cur.fetchone()

    assert row is not None
    line_m, edges_m = row
    assert route["geometry"]["type"] == "LineString"
    assert line_m == pytest.approx(route["length_m"], rel=1e-3)
    assert edges_m == pytest.approx(route["length_m"])


async def test_route_runs_from_start_to_finish_at_about_the_target(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    await grid(admin_conn, mapper_pool)

    route = await plan(api_pool, "running", CENTRE, EAST, 3_000)

    assert route["length_m"] == pytest.approx(3_000, rel=TOLERANCE)
    assert route["warnings"] == []
    assert ends(route) == (coordinates(12, 12), coordinates(20, 12))


async def test_long_route_to_a_near_finish_does_not_retrace(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    await grid(admin_conn, mapper_pool)

    # About seven times the direct distance.
    route = await plan(api_pool, "running", grid_point(10, 12), grid_point(14, 12), 3_500)

    assert route["length_m"] == pytest.approx(3_500, rel=TOLERANCE)
    assert route["reused_m"] < 0.05 * route["length_m"]


async def test_route_takes_the_way_with_fewest_turns(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    await grid(admin_conn, mapper_pool)
    # A staircase north-east, a little greener than the streets around it.
    steps = [(node_id(4 + k, 4 + k), node_id(5 + k, 4 + k)) for k in range(8)] + [
        (node_id(5 + k, 4 + k), node_id(5 + k, 5 + k)) for k in range(8)
    ]
    await admin_conn.execute(
        """
        UPDATE graph.edges SET scores = '{"green": 0.2}'
        WHERE (source, target) IN (SELECT * FROM unnest(%s::bigint[], %s::bigint[]))
        """,
        ([a for a, _ in steps], [b for _, b in steps]),
    )
    vias = [node_id(4, 4), node_id(12, 12)]

    free = await route_ways(api_pool, vias, {"green": 1}, turn_m=0)
    paid = await route_ways(api_pool, vias, {"green": 1})

    assert turns(free) == 15
    # As long, but 14 turns fewer for a little less green.
    assert (len(paid), turns(paid)) == (16, 1)


async def path_and_road(conn: Conn, mapper_pool: Pool) -> None:
    """A path 1 -> 2 -> 3 of 2 x 114 m, and a road of 450 m from 3 back round to 1. 2 is where
    the path is split, so going back from there is shorter than going on, but not by what
    turning round costs."""
    path = {"highway": "footway"}
    await add_line(conn, 10, [(1, 0, 0), (2, 2, 0)], path)
    await add_line(conn, 11, [(2, 2, 0), (3, 4, 0)], path)
    await add_line(conn, 12, [(3, 4, 0), (4, 4, 1), (5, 0, 1), (1, 0, 0)], STREET)
    await map_pending(mapper_pool.connection)


async def test_route_carries_on_past_a_via_instead_of_doubling_back(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    await path_and_road(admin_conn, mapper_pool)

    async with api_pool.connection() as conn:
        # Routed from b alone, with the path behind it already used, the way back is shortest.
        cur = await conn.execute(
            """
            SELECT e.way_id
            FROM pgr_dijkstra(
                     routing.cost_sql(
                         routing.make_profile('running'), NULL,
                         ARRAY(SELECT id FROM graph.edges WHERE way_id = 10)
                     ),
                     2, 1
                 ) d
            JOIN graph.edges e ON e.id = d.edge
            """
        )
        alone = [way_id for (way_id,) in await cur.fetchall()]

    ways = await route_ways(api_pool, [1, 2, 1])

    assert alone == [10]
    assert ways == [10, 11, 12]


async def test_evaluation_measures_a_via_as_the_route_will_pass_it(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    await path_and_road(admin_conn, mapper_pool)

    async with api_pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT (e).length_m, (e).doubled_m,
                   (SELECT sum(length_m) FROM graph.edges)
            FROM routing.evaluate(
                     routing.make_profile('running'), NULL, 1000,
                     ARRAY[ROW('{1, 2, 1}')]::routing.candidate[]
                 ) e
            """
        )
        row = await cur.fetchone()

    assert row is not None
    length_m, doubled_m, network_m = row
    # Out to 2 and back would be shortest, but the route goes on and round by the road.
    assert length_m == pytest.approx(network_m)
    assert doubled_m == 0


async def test_candidate_that_must_turn_round_at_a_via_scores_as_missing_the_target(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    # A path 1 -> 2 -> 3 that ends at 3: from 2 there is no way on that does not come back.
    path = {"highway": "footway"}
    await add_line(admin_conn, 10, [(1, 0, 0), (2, 2, 0)], path)
    await add_line(admin_conn, 11, [(2, 2, 0), (3, 4, 0)], path)
    await map_pending(mapper_pool.connection)

    async with api_pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT (e).length_m, (e).score
            FROM routing.evaluate(
                     routing.make_profile('running'), NULL, 228,
                     ARRAY[ROW('{1, 2, 1}')]::routing.candidate[]
                 ) e
            """
        )
        row = await cur.fetchone()

    assert row is not None
    length_m, score = row
    # Out and back is the target exactly; only turning round costs.
    assert length_m == pytest.approx(228, rel=0.01)
    assert score > 1


async def test_route_goes_round_instead_of_taking_a_hairpin(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    # A road east to 2, where a path of 254 m forks back at about 155 degrees to 3, and the road
    # goes on round to 3 the long way, 567 m.
    await add_line(admin_conn, 10, [(1, 0, 0), (2, 4, 0)], STREET)
    await add_line(admin_conn, 11, [(2, 4, 0), (3, 0, 1)], {"highway": "footway"})
    await add_line(admin_conn, 12, [(2, 4, 0), (4, 6, 0), (5, 6, 1), (3, 0, 1)], STREET)
    await map_pending(mapper_pool.connection)

    async with api_pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT e.way_id
            FROM pgr_dijkstra(routing.cost_sql(routing.make_profile('running'), NULL), 1, 3) d
            JOIN graph.edges e ON e.id = d.edge
            ORDER BY d.seq
            """
        )
        shortest = [way_id for (way_id,) in await cur.fetchall()]

    ways = await route_ways(api_pool, [1, 3])

    assert shortest == [10, 11]
    assert ways == [10, 12]


async def test_bow_leaves_at_a_right_angle_and_stays_beside_the_way(api_pool: Pool) -> None:
    async with api_pool.connection() as conn:
        cur = await conn.execute(
            """
            WITH ends AS (
                SELECT ST_Point(20, 63, 4326) AS a,
                       ST_Project(ST_Point(20, 63, 4326)::geography, 1000, radians(90))::geometry
                           AS b
            )
            SELECT f,
                   ST_Distance(a::geography, p::geography) AS from_start_m,
                   degrees(ST_Azimuth(a::geography, p::geography)) AS bearing
            FROM ends, unnest(ARRAY[0.05, 0.5, 0.95]) f,
                 routing.bow_point(a, b, routing.bow_height(2), 1, f) p
            ORDER BY f
            """
        )
        rows = await cur.fetchall()

    # Twice as long as the 1 km east: up to the left, the middle about 760 m north of the way.
    (_, near_m, near_bearing), (_, middle_m, middle_bearing), (_, end_m, end_bearing) = rows
    assert near_bearing == pytest.approx(0, abs=10)
    assert near_m < 200
    assert middle_m * math.cos(math.radians(middle_bearing)) == pytest.approx(760, rel=0.02)
    # Near the finish, beside the way but not past it.
    assert 0 < end_bearing < 90
    assert end_m * math.sin(math.radians(end_bearing)) <= 1_000


async def test_doubled_counts_going_back_alongside_but_not_crossing(api_pool: Pool) -> None:
    async with api_pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT routing.doubled_m(ST_MakeLine(ARRAY[
                       ST_Point(20, 63.8, 4326), ST_Point(20.01, 63.8, 4326),
                       ST_Point(20.01, 63.8001, 4326), ST_Point(20, 63.8001, 4326)
                   ])),
                   routing.doubled_m(ST_MakeLine(ARRAY[
                       ST_Point(20, 63.8, 4326), ST_Point(20.02, 63.8, 4326),
                       ST_Point(20.02, 63.81, 4326), ST_Point(20.01, 63.81, 4326),
                       ST_Point(20.01, 63.79, 4326)
                   ]))
            """
        )
        row = await cur.fetchone()

    assert row is not None
    back_alongside, crossing = row
    # Out about 500 m and back 11 m beside it: all but the 300 m around the turn.
    assert back_alongside == pytest.approx(700, rel=0.1)
    assert crossing == 0


async def test_route_to_a_finish_does_not_set_off_behind_the_start(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    await grid(admin_conn, mapper_pool)

    # Twice the 12 blocks east of the start.
    route = await plan(api_pool, "running", grid_point(6, 12), grid_point(18, 12), 2_750)

    assert route["length_m"] == pytest.approx(2_750, rel=TOLERANCE)
    start_lon = ORIGIN_LON + 6 * COLUMN_STEPS * STEP
    finish_lon = ORIGIN_LON + 18 * COLUMN_STEPS * STEP
    lons = [lon for lon, _ in route["geometry"]["coordinates"]]
    assert start_lon <= min(lons) and max(lons) <= finish_lon


async def test_target_below_the_direct_route_takes_it_with_a_warning(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    await grid(admin_conn, mapper_pool)

    route = await plan(api_pool, "running", CENTRE, EAST, 500)

    # Eight blocks east along row 12.
    assert route["length_m"] == pytest.approx(8 * 113.7, rel=0.01)
    assert route["warnings"] == ["too_short"]


async def test_loop_heads_for_the_park_when_green_is_preferred(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool, api_pool: Pool
) -> None:
    await add_grid(admin_conn, STREET)
    # North-west of the centre, columns 2 to 10 and rows 14 to 22.
    park = (2 * COLUMN_STEPS, 14, 10 * COLUMN_STEPS, 22)
    await add_square(admin_conn, 1_001, 1_001, park, {"leisure": "park"})
    await run(mapper_pool, enricher_pool)

    preferred = await plan(api_pool, "running", CENTRE, None, 4_000, {"green": 1})
    avoided = await plan(api_pool, "running", CENTRE, None, 4_000, {"green": -1})

    assert preferred["scores"]["green"] > 0.5
    assert avoided["scores"]["green"] < 0.1
    assert preferred["length_m"] == pytest.approx(4_000, rel=TOLERANCE)


async def test_cycling_follows_one_way_streets(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    await grid(admin_conn, mapper_pool, one_way_rows=frozenset(range(0, 25, 2)))

    async with api_pool.connection() as conn:
        cur = await conn.execute(
            """
            WITH p AS (SELECT routing.make_profile('cycling') AS p)
            SELECT bool_and(CASE WHEN r.vertex = a.source THEN a.forward ELSE a.backward END),
                   count(*)
            FROM p,
                 routing.route_edges(p.p, NULL, ARRAY[%(start)s, %(east)s, %(start)s]::bigint[]) r
            JOIN routing.activity_edges a ON a.id = r.edge_id AND a.activity = 'cycling'
            """,
            {"start": node_id(12, 12), "east": node_id(4, 12)},
        )
        row = await cur.fetchone()

    assert row is not None
    allowed, edges = row
    assert edges > 0
    assert allowed


async def test_start_far_from_any_road_is_an_error(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    await grid(admin_conn, mapper_pool)

    with pytest.raises(psycopg.errors.NoDataFound, match="no road near the start"):
        await plan(api_pool, "running", grid_point(12, 40), None, 3_000)


async def test_unreachable_finish_is_an_error(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    await grid(admin_conn, mapper_pool)
    island = f"SRID=4326;POINT({ORIGIN_LON + 0.1} {ORIGIN_LAT})"
    await admin_conn.execute(
        "INSERT INTO raw.osm_nodes (id, tags, geom) VALUES (1, '{}', %s), (2, '{}', %s)",
        (island, f"SRID=4326;POINT({ORIGIN_LON + 0.1 + STEP} {ORIGIN_LAT})"),
    )
    await admin_conn.execute(
        "INSERT INTO raw.osm_ways (id, tags, node_ids) VALUES (999, %s, '{1, 2}')", (Jsonb(STREET),)
    )
    await map_pending(mapper_pool.connection)

    with pytest.raises(psycopg.errors.NoDataFound, match="cannot be reached"):
        await plan(api_pool, "running", CENTRE, island, 9_000)


@pytest.mark.parametrize(
    ("target_m", "options"),
    [
        (0, {}),
        (3_000, {"tolerance": 0}),
        (3_000, {"snap": 50}),
        (3_000, {"snap_m": -1}),
        (3_000, {"turn_m": -1}),
    ],
)
async def test_bad_target_or_options_are_rejected(
    api_pool: Pool, target_m: float, options: dict[str, float]
) -> None:
    with pytest.raises(psycopg.errors.InvalidParameterValue):
        await plan(api_pool, "running", CENTRE, None, target_m, options=options)
