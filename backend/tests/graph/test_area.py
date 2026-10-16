import pytest
from psycopg_pool import AsyncConnectionPool

from app.graph import map_pending
from app.graph.area import AreaTooLarge, graph_in_bounds
from app.sources.tiles import Bounds

from .raw_data import ORIGIN_LAT, ORIGIN_LON, STEP, Conn, add_line

pytestmark = pytest.mark.db

type Pool = AsyncConnectionPool[Conn]


def box(x_min: float, y_min: float, x_max: float, y_max: float) -> Bounds:
    """Bounds in grid steps, as raw_data places nodes."""
    return Bounds(
        west=ORIGIN_LON + x_min * STEP,
        south=ORIGIN_LAT + y_min * STEP,
        east=ORIGIN_LON + x_max * STEP,
        north=ORIGIN_LAT + y_max * STEP,
    )


async def build(conn: Conn, mapper_pool: Pool) -> None:
    """A street 1-2-3 along y = 0 with a footpath 2-4 going north from its middle."""
    await add_line(
        conn, 10, [(1, 0, 0), (2, 2, 0), (3, 4, 0)], {"highway": "residential", "name": "Main"}
    )
    await add_line(conn, 11, [(2, 2, 0), (4, 2, 2)], {"highway": "footway"})
    await map_pending(mapper_pool.connection)


async def test_area_returns_edges_with_their_way_and_vertices(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    await build(admin_conn, mapper_pool)

    async with api_pool.connection() as conn:
        area = await graph_in_bounds(conn, box(-1, -1, 5, 3), max_edges=10)

    assert [(e.way_id, e.source, e.target) for e in area.edges] == [
        (10, 1, 2),
        (10, 2, 3),
        (11, 2, 4),
    ]
    assert [e.id for e in area.edges] == sorted(e.id for e in area.edges)
    street = area.edges[0]
    assert street.tags == {"highway": "residential", "name": "Main"}
    assert street.forward == ["cycling", "running"]
    assert street.backward == ["cycling", "running"]
    assert street.scores == {}
    assert street.length_m == pytest.approx(113.7, abs=0.5)
    assert street.geometry == {
        "type": "LineString",
        "coordinates": [[18.0, 59.3], [18.002, 59.3]],
    }
    assert [v.id for v in area.vertices] == [1, 2, 3, 4]
    assert area.vertices[3].geometry == {"type": "Point", "coordinates": [18.002, 59.302]}


async def test_edge_crossing_the_border_comes_whole(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    await build(admin_conn, mapper_pool)

    # Holds only the middle of the footpath: neither of its vertices is inside.
    async with api_pool.connection() as conn:
        area = await graph_in_bounds(conn, box(1.5, 0.5, 2.5, 1.5), max_edges=10)

    assert [(e.way_id, e.source, e.target) for e in area.edges] == [(11, 2, 4)]
    assert area.edges[0].geometry["coordinates"] == [[18.002, 59.3], [18.002, 59.302]]
    assert [v.id for v in area.vertices] == [2, 4]


async def test_area_without_edges_is_empty(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    await build(admin_conn, mapper_pool)

    async with api_pool.connection() as conn:
        area = await graph_in_bounds(conn, box(10, 10, 12, 12), max_edges=10)

    assert (area.edges, area.vertices) == ([], [])


async def test_area_at_the_limit_is_returned_and_one_above_is_refused(
    admin_conn: Conn, mapper_pool: Pool, api_pool: Pool
) -> None:
    await build(admin_conn, mapper_pool)

    async with api_pool.connection() as conn:
        assert len((await graph_in_bounds(conn, box(-1, -1, 5, 3), max_edges=3)).edges) == 3
        with pytest.raises(AreaTooLarge, match="more than 2 edges"):
            await graph_in_bounds(conn, box(-1, -1, 5, 3), max_edges=2)


@pytest.mark.parametrize(
    ("bounds", "message"),
    [
        (Bounds(west=18.1, south=59.3, east=18.0, north=59.4), "West"),
        (Bounds(west=18.0, south=59.4, east=18.1, north=59.3), "South"),
    ],
)
async def test_inside_out_bounds_are_refused(
    admin_conn: Conn, api_pool: Pool, bounds: Bounds, message: str
) -> None:
    async with api_pool.connection() as conn:
        with pytest.raises(ValueError, match=message):
            await graph_in_bounds(conn, bounds, max_edges=10)
