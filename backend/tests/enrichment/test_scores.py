import math

import pytest

from ..graph.raw_data import Conn, add_node, add_way
from .area_data import Pool, add_relation, add_road, add_square, run, scores

pytestmark = pytest.mark.db

PARK = {"leisure": "park"}

# Grid steps are about 57 m east-west and 111 m north-south. The park spans 570 m x 1110 m.
PARK_BOX = (0, 0, 10, 10)
MIDDLE = 200  # (3, 5) to (7, 5): more than 25 m from every park node and side
SIDE = 300  # (0, 3) to (0, 7): on the west side
FAR = 400  # (50, 3) to (50, 7)


async def roads(conn: Conn) -> None:
    await add_road(conn, MIDDLE, (201, 3, 5), (202, 7, 5))
    await add_road(conn, SIDE, (301, 0, 3), (302, 0, 7))
    await add_road(conn, FAR, (401, 50, 3), (402, 50, 7))


async def test_path_through_the_middle_of_a_park_is_fully_green(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square(admin_conn, 101, 1, PARK_BOX, PARK)
    await roads(admin_conn)

    await run(mapper_pool, enricher_pool)

    green = (await scores(admin_conn))[MIDDLE]["green"]
    assert green == pytest.approx(1, abs=1e-6)
    assert green <= 1


async def test_road_along_a_park_is_half_green(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square(admin_conn, 101, 1, PARK_BOX, PARK)
    await roads(admin_conn)

    await run(mapper_pool, enricher_pool)

    assert (await scores(admin_conn))[SIDE]["green"] == pytest.approx(0.5, abs=1e-3)


async def test_road_without_a_park_is_scored_zero(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await roads(admin_conn)

    await run(mapper_pool, enricher_pool)

    assert (await scores(admin_conn))[FAR] == {"green": 0}


async def test_overlapping_parks_count_once(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square(admin_conn, 101, 1, PARK_BOX, PARK)
    await add_square(admin_conn, 102, 5, (2, 2, 8, 8), PARK)
    await roads(admin_conn)

    await run(mapper_pool, enricher_pool)

    assert (await scores(admin_conn))[MIDDLE]["green"] <= 1


@pytest.mark.parametrize("lat", [59.3, 0.5])
async def test_the_corridor_is_25_m_wide_at_any_latitude(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool, lat: float
) -> None:
    # A north-south road with a park starting 12.5 m east of it and reaching past both ends.
    offset_deg = 12.5 / (111320 * math.cos(math.radians(lat)))
    await admin_conn.execute(
        """
        INSERT INTO raw.osm_nodes (id, tags, geom) VALUES
            (1, '{}', ST_Point(18, %(lat)s, 4326)),
            (2, '{}', ST_Point(18, %(lat)s + 0.002, 4326)),
            (11, '{}', ST_Point(18 + %(dx)s, %(lat)s - 0.01, 4326)),
            (12, '{}', ST_Point(18.01, %(lat)s - 0.01, 4326)),
            (13, '{}', ST_Point(18.01, %(lat)s + 0.012, 4326)),
            (14, '{}', ST_Point(18 + %(dx)s, %(lat)s + 0.012, 4326))
        """,
        {"lat": lat, "dx": offset_deg},
    )
    await add_way(admin_conn, 1, [1, 2], {"highway": "path"})
    await add_way(admin_conn, 101, [11, 12, 13, 14, 11], PARK)

    await run(mapper_pool, enricher_pool)

    cur = await admin_conn.execute("SELECT length_m FROM graph.edges")
    row = await cur.fetchone()
    assert row is not None
    length_m: float = row[0]
    r, d = 25, 12.5
    # The strip from 12.5 m to 25 m east, plus the matching part of the two end caps.
    cap_part = r**2 * math.acos(d / r) - d * math.sqrt(r**2 - d**2)
    expected = (d * length_m + cap_part) / (2 * r * length_m + math.pi * r**2)
    assert (await scores(admin_conn))[1]["green"] == pytest.approx(expected, rel=0.01)


async def test_park_arriving_later_rescores_unchanged_roads(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await roads(admin_conn)
    await run(mapper_pool, enricher_pool)

    await add_square(admin_conn, 101, 1, PARK_BOX, PARK)
    result = await run(mapper_pool, enricher_pool)

    assert (await scores(admin_conn))[MIDDLE]["green"] == pytest.approx(1, abs=1e-6)
    assert (await scores(admin_conn))[FAR] == {"green": 0}
    assert sum(b.edges_queued for b in result.batches) == 2  # MIDDLE and SIDE


async def test_removed_park_rescores_its_roads(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square(admin_conn, 101, 1, PARK_BOX, PARK)
    await roads(admin_conn)
    await run(mapper_pool, enricher_pool)

    await add_way(admin_conn, 101, [1, 2, 3, 4, 1], {})
    await run(mapper_pool, enricher_pool)

    assert (await scores(admin_conn))[MIDDLE] == {"green": 0}


async def test_moving_a_park_node_rescores_roads_near_the_new_shape(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square(admin_conn, 101, 1, PARK_BOX, PARK)
    # Just east of the park, more than 25 m from it.
    await add_road(admin_conn, 500, (501, 11, 8), (502, 11, 9))
    await run(mapper_pool, enricher_pool)
    assert (await scores(admin_conn))[500] == {"green": 0}

    # The north-east corner moves east; the road is now well inside.
    await add_node(admin_conn, 3, 20, 10)
    await run(mapper_pool, enricher_pool)

    assert (await scores(admin_conn))[500]["green"] == pytest.approx(1, abs=1e-6)


async def test_renamed_park_rescores_nothing(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square(admin_conn, 101, 1, PARK_BOX, PARK)
    await roads(admin_conn)
    await run(mapper_pool, enricher_pool)

    await add_way(admin_conn, 101, [1, 2, 3, 4, 1], {**PARK, "name": "Renamed"})
    result = await run(mapper_pool, enricher_pool)

    assert sum(b.edges_queued for b in result.batches) == 0
    assert sum(b.edges_scored for b in result.batches) == 0


async def test_multipolygon_hole_is_not_green(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square(admin_conn, 20, 1, (0, 0, 20, 20), {})
    await add_square(admin_conn, 22, 5, (5, 5, 15, 15), {})
    await add_relation(
        admin_conn, 30, [(20, "outer"), (22, "inner")], {"leisure": "park", "type": "multipolygon"}
    )
    # In the middle of the hole, more than 25 m from its edge.
    await add_road(admin_conn, 600, (601, 9, 10), (602, 11, 10))

    await run(mapper_pool, enricher_pool)

    assert (await scores(admin_conn))[600] == {"green": 0}
