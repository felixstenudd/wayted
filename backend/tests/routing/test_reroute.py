from typing import Any

import psycopg
import pytest

from ..graph.raw_data import Conn
from .network_data import grid_point, node_id
from .test_planner import Pool, coordinates, ends, grid, passed, plan

pytestmark = pytest.mark.db

WEST = grid_point(2, 12)
EAST = grid_point(22, 12)


async def reroute(
    pool: Pool,
    route: dict[str, Any],
    grab: str,
    drop: str | None,
    target_m: float | None = None,
    activity: str = "running",
) -> dict[str, Any]:
    steps = route["edges"]
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT routing.reroute(%s, %s::bigint[], %s::boolean[], %s, %s, %s)",
            (
                activity,
                [s["edge_id"] for s in steps],
                [s["forward"] for s in steps],
                grab,
                drop,
                target_m,
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
