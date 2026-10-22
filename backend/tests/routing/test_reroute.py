from typing import Any

import psycopg
import pytest

from ..graph.raw_data import ORIGIN_LAT, ORIGIN_LON, STEP, Conn
from .network_data import COLUMN_STEPS, grid_point, node_id
from .test_planner import Pool, coordinates, ends, grid, passed, plan

pytestmark = pytest.mark.db

ORIGINS = (ORIGIN_LON, ORIGIN_LAT)
STEPS = (COLUMN_STEPS * STEP, STEP)

WEST = grid_point(2, 12)
EAST = grid_point(22, 12)


async def reroute(
    pool: Pool,
    route: dict[str, Any],
    grab: str,
    drop: str | None,
    target_m: float | None = None,
    reach: tuple[float, float] | None = None,
    activity: str = "running",
) -> dict[str, Any]:
    steps = route["edges"]
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT routing.reroute(%s, %s::bigint[], %s::boolean[], %s, %s, %s, %s, %s)",
            (
                activity,
                [s["edge_id"] for s in steps],
                [s["forward"] for s in steps],
                grab,
                drop,
                target_m,
                *(reach or (None, None)),
            ),
        )
        row = await cur.fetchone()
    assert row is not None
    rerouted: dict[str, Any] = row[0]
    return rerouted


async def straight(admin_conn: Conn, mapper_pool: Pool, api_pool: Pool) -> dict[str, Any]:
    """Twenty blocks east along row 12, the cheapest way."""
    await grid(admin_conn, mapper_pool)
    route = await plan(api_pool, "running", WEST, EAST, None, settings={"options": {"count": 1}})
    assert route["length_m"] == pytest.approx(20 * 113.7, rel=0.01)
    return route


async def test_dragging_the_line_onto_a_street_takes_the_route_along_it(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    route = await straight(admin_conn, mapper_pool, api_pool)

    # Grabbed in the middle and dropped two rows north, between two crossings.
    edited = await reroute(api_pool, route, grid_point(12, 12), grid_point(12.5, 14))

    _, off_m = await passed(api_pool, edited, 12.5, 14)
    assert off_m < 1
    assert ends(edited) == (coordinates(2, 12), coordinates(22, 12))
    # Up two rows and back down again.
    assert edited["length_m"] == pytest.approx(20 * 113.7 + 4 * 111.2, rel=0.01)
    assert edited["handle"]["coordinates"] == pytest.approx(coordinates(12.5, 14))


async def test_only_the_stretch_around_the_grab_changes(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    route = await straight(admin_conn, mapper_pool, api_pool)

    edited = await reroute(api_pool, route, grid_point(12, 12), grid_point(12.5, 14))

    # The window reaches 300 m or 1.5 times the drag either side, about four blocks here.
    before, after = route["edges"], edited["edges"]
    assert after[:4] == before[:4]
    assert after[-4:] == before[-4:]


async def along(pool: Pool, crossings: list[tuple[int, int]]) -> dict[str, Any]:
    """A route through grid crossings (column, row) next to each other, as its edges."""
    nodes = [node_id(c, r) for c, r in crossings]
    async with pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT e.id, e.source = s.a
            FROM unnest(%s::bigint[], %s::bigint[]) WITH ORDINALITY AS s (a, b, n)
            JOIN graph.edges e ON (e.source, e.target) IN ((s.a, s.b), (s.b, s.a))
            ORDER BY s.n
            """,
            (nodes[:-1], nodes[1:]),
        )
        rows = await cur.fetchall()
    assert len(rows) == len(nodes) - 1
    return {"edges": [{"edge_id": i, "forward": f} for i, f in rows]}


async def test_without_a_drop_the_stretch_takes_the_plain_way_again(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    await grid(admin_conn, mapper_pool)
    # East along row 12, with a block up and back down at column 12, as an edit can leave it.
    spur = await along(
        api_pool,
        [(c, 12) for c in range(2, 13)] + [(12, 13)] + [(c, 12) for c in range(12, 23)],
    )

    plain = await reroute(api_pool, spur, grid_point(12, 13), None)

    assert plain["length_m"] == pytest.approx(20 * 113.7, rel=0.01)
    assert ends(plain) == (coordinates(2, 12), coordinates(22, 12))
    assert plain["handle"] is None


async def test_edited_route_is_scored_and_warned_like_a_planned_one(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    route = await straight(admin_conn, mapper_pool, api_pool)

    edited = await reroute(api_pool, route, grid_point(12, 12), grid_point(12.5, 14), 2_300)

    assert edited["warnings"] == ["target_missed"]
    assert set(edited) >= {"geometry", "length_m", "scores", "reused_m", "edges"}


async def test_drop_far_from_any_road_is_an_error(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    route = await straight(admin_conn, mapper_pool, api_pool)

    with pytest.raises(psycopg.errors.NoDataFound) as raised:
        await reroute(api_pool, route, grid_point(12, 12), grid_point(12, 40))

    assert raised.value.diag.message_detail == "drop_off_road"


async def test_edges_that_do_not_join_up_are_rejected(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    route = await straight(admin_conn, mapper_pool, api_pool)
    broken = {**route, "edges": route["edges"][:3] + route["edges"][5:]}

    with pytest.raises(psycopg.errors.InvalidParameterValue):
        await reroute(api_pool, broken, grid_point(12, 12), grid_point(12.5, 14))


def turns_back(route: dict[str, Any]) -> list[int]:
    """Edges the route travels and then straight back along: a spur."""
    steps = route["edges"]
    return [
        a["edge_id"]
        for a, b in zip(steps, steps[1:], strict=False)
        if a["edge_id"] == b["edge_id"] and a["forward"] != b["forward"]
    ]


@pytest.mark.parametrize(
    ("grab", "drop"),
    [
        ((12, 12), (12.5, 14)),
        ((12, 12), (9.5, 13)),
        ((12, 12), (14.5, 11)),
        ((6, 12), (5.5, 13)),
        ((18, 12), (18.5, 10)),
    ],
)
async def test_an_edit_carries_on_the_way_the_route_was_going(
    admin_conn: Conn,
    mapper_pool: Pool,
    api_pool: Pool,
    grab: tuple[float, float],
    drop: tuple[float, float],
) -> None:
    route = await straight(admin_conn, mapper_pool, api_pool)

    edited = await reroute(api_pool, route, grid_point(*grab), grid_point(*drop))

    assert turns_back(edited) == []
    assert ends(edited) == (coordinates(2, 12), coordinates(22, 12))


async def test_dropping_on_a_road_from_the_start_carries_on_from_it(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    route = await straight(admin_conn, mapper_pool, api_pool)

    # Grabbed a block from the start and dropped on the street leading north from it.
    edited = await reroute(api_pool, route, grid_point(3, 12), grid_point(2, 12.5))

    assert turns_back(edited) == []
    _, off_m = await passed(api_pool, edited, 2, 12.5)
    assert off_m < 1
    assert ends(edited) == (coordinates(2, 12), coordinates(22, 12))


async def test_a_change_comes_back_out_over_the_stretch_it_moved(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    route = await straight(admin_conn, mapper_pool, api_pool)
    # A long drag, four rows north, moves a long stretch.
    edited = await reroute(api_pool, route, grid_point(12, 12), grid_point(12.5, 16))
    handle = edited["handle"]["coordinates"]
    at = grid_point(*[(c - o) / s for c, o, s in zip(handle, ORIGINS, STEPS, strict=True)])

    undone = await reroute(
        api_pool, edited, at, None, reach=(edited["before_m"], edited["after_m"])
    )

    assert edited["before_m"] > 300
    assert undone["length_m"] == pytest.approx(route["length_m"], rel=0.01)
