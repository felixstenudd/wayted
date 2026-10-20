from typing import Any

import psycopg
import pytest
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from app.graph import map_pending

from ..enrichment.area_data import add_square, run
from ..graph.raw_data import ORIGIN_LAT, ORIGIN_LON, STEP, Conn
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
    [(0, {}), (3_000, {"tolerance": 0}), (3_000, {"snap": 50}), (3_000, {"snap_m": -1})],
)
async def test_bad_target_or_options_are_rejected(
    api_pool: Pool, target_m: float, options: dict[str, float]
) -> None:
    with pytest.raises(psycopg.errors.InvalidParameterValue):
        await plan(api_pool, "running", CENTRE, None, target_m, options=options)
