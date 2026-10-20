import pytest

from ..graph.raw_data import Conn, add_way, pending_edges
from .area_data import Pool, add_node_m, run, scores

pytestmark = pytest.mark.db

LAKE = {"natural": "water"}
PATH = {"highway": "path"}


async def add_square_m(
    conn: Conn, way_id: int, first_node: int, box: tuple[float, float, float, float]
) -> None:
    """A lake over (west, south, east, north) in metres."""
    west, south, east, north = box
    for offset, (x, y) in enumerate([(west, south), (east, south), (east, north), (west, north)]):
        await add_node_m(conn, first_node + offset, x, y)
    await add_way(conn, way_id, [first_node + offset for offset in (0, 1, 2, 3, 0)], LAKE)


async def add_line_m(
    conn: Conn,
    way_id: int,
    first_node: int,
    a: tuple[float, float],
    b: tuple[float, float],
    tags: dict[str, str],
) -> None:
    await add_node_m(conn, first_node, *a)
    await add_node_m(conn, first_node + 1, *b)
    await add_way(conn, way_id, [first_node, first_node + 1], tags)


async def add_path_m(
    conn: Conn, way_id: int, east_m: float, south_m: float, north_m: float
) -> None:
    """A north-south path at east_m, nodes way_id * 10 and way_id * 10 + 1."""
    await add_line_m(conn, way_id, way_id * 10, (east_m, south_m), (east_m, north_m), PATH)


async def water(conn: Conn, way_id: int) -> float:
    return (await scores(conn))[way_id]["water"]


async def test_path_through_a_lake_is_fully_water(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square_m(admin_conn, 101, 1, (0, 0, 1000, 1000))
    await add_path_m(admin_conn, 200, 500, 400, 600)

    await run(mapper_pool, enricher_pool)

    assert await water(admin_conn, 200) == pytest.approx(1, abs=1e-6)


async def test_path_along_a_lake_shore_falls_off_with_distance(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square_m(admin_conn, 101, 1, (0, 0, 1000, 1000))
    await add_path_m(admin_conn, 200, -20, 300, 700)

    await run(mapper_pool, enricher_pool)

    assert await water(admin_conn, 200) == pytest.approx(1 - (20 / 50) ** 2, abs=1e-2)


async def test_path_along_a_river_line(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_line_m(admin_conn, 101, 1, (0, 0), (0, 1000), {"waterway": "river"})
    await add_path_m(admin_conn, 200, 10, 300, 700)

    await run(mapper_pool, enricher_pool)

    assert await water(admin_conn, 200) == pytest.approx(1 - (10 / 50) ** 2, abs=1e-2)


async def test_path_along_the_coastline(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_line_m(admin_conn, 101, 1, (0, 0), (0, 1000), {"natural": "coastline"})
    await add_path_m(admin_conn, 200, 30, 300, 700)

    await run(mapper_pool, enricher_pool)

    assert await water(admin_conn, 200) == pytest.approx(1 - (30 / 50) ** 2, abs=1e-2)


async def test_path_beyond_50_m_is_zero(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square_m(admin_conn, 101, 1, (0, 0, 1000, 1000))
    await add_path_m(admin_conn, 200, -60, 300, 700)

    await run(mapper_pool, enricher_pool)

    assert await water(admin_conn, 200) == 0


async def test_half_of_a_path_near_water_scores_half(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    # 400 m east-west from inside the lake out to 200 m from it: 200 m at 1, 150 m at 0, and a
    # 50 m falloff that averages 2/3.
    await add_square_m(admin_conn, 101, 1, (0, 0, 1000, 1000))
    await add_line_m(admin_conn, 200, 2000, (800, 500), (1200, 500), PATH)

    await run(mapper_pool, enricher_pool)

    assert await water(admin_conn, 200) == pytest.approx((200 + 50 * 2 / 3) / 400, abs=1e-2)


async def test_short_edge_takes_one_sample(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square_m(admin_conn, 101, 1, (0, 0, 1000, 1000))
    await add_path_m(admin_conn, 200, -20, 500, 505)

    await run(mapper_pool, enricher_pool)

    assert await water(admin_conn, 200) == pytest.approx(1 - (20 / 50) ** 2, abs=1e-2)


async def test_large_lake_clipped_to_the_box_scores_the_same(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square_m(admin_conn, 101, 1, (-20_000, -20_000, 0, 20_000))
    await add_path_m(admin_conn, 200, 20, 300, 700)

    await run(mapper_pool, enricher_pool)

    assert await water(admin_conn, 200) == pytest.approx(1 - (20 / 50) ** 2, abs=1e-2)


async def test_overlapping_lake_and_river_count_the_nearer(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square_m(admin_conn, 101, 1, (0, 0, 1000, 1000))
    await add_line_m(admin_conn, 102, 11, (30, 0), (30, 1000), {"waterway": "river"})
    await add_path_m(admin_conn, 200, 0, 300, 700)

    await run(mapper_pool, enricher_pool)

    assert await water(admin_conn, 200) == pytest.approx(1, abs=1e-6)


async def test_lake_arriving_later_rescores_roads_within_50_m(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_path_m(admin_conn, 200, -40, 300, 700)
    await add_path_m(admin_conn, 300, -200, 300, 700)
    await run(mapper_pool, enricher_pool)

    await add_square_m(admin_conn, 101, 1, (0, 0, 1000, 1000))
    result = await run(mapper_pool, enricher_pool)

    assert await water(admin_conn, 200) == pytest.approx(1 - (40 / 50) ** 2, abs=1e-2)
    assert await water(admin_conn, 300) == 0
    assert sum(b.edges_queued for b in result.batches) == 1
    assert await pending_edges(admin_conn) == set()
