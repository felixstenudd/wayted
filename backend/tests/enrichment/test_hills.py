import math

import pytest

from app.enrichment import enrich_pending
from app.enrichment.definitions import HILLS
from app.sources.tiles import Tile

from ..graph.raw_data import ORIGIN_LAT, ORIGIN_LON, Conn, add_line, add_way
from .area_data import Pool, add_node_m, add_road, run, scores

pytestmark = pytest.mark.db

# The height model under the roads: cells of 0.0002 by 0.0001 degrees from 17.995 to 18.055
# east and 59.300 to 59.312 north. Roads run east along row 5 of the raw_data grid (59.305).
COLUMN_M = 0.0002 * 111_320 * math.cos(math.radians(ORIGIN_LAT + 0.005))
TILE = Tile.from_lat_lon(ORIGIN_LAT + 0.005, 18.01, 14)
EAST = 100  # (1, 5) to (49, 5), about 2.7 km


def grade(share: float) -> str:
    """Heights rising east by share of the distance."""
    return f"[rast.x] * {share * COLUMN_M}"


async def add_heights(conn: Conn, heights: str) -> None:
    """The height model as one elevation tile, each cell as high as the map algebra expression."""
    await conn.execute(
        """
        INSERT INTO raw.elevation_tiles (z, x, y, rast)
        SELECT %(z)s, %(x)s, %(y)s, ST_MapAlgebra(
            ST_AddBand(
                ST_MakeEmptyRaster(300, 120, 17.995, 59.312, 0.0002, -0.0001, 0, 0, 4326),
                '32BF'::text, 0, -32767
            ),
            1, '32BF', %(heights)s
        )
        ON CONFLICT (z, x, y) DO UPDATE SET rast = EXCLUDED.rast
        """,
        {"z": TILE.z, "x": TILE.x, "y": TILE.y, "heights": heights},
    )


async def hills(conn: Conn, way_id: int) -> float:
    return (await scores(conn))[way_id]["hills"]


async def climb(conn: Conn, way_id: int) -> tuple[float | None, float | None, float]:
    """The way's one edge: metres climbed and dropped from source to target, and its length."""
    cur = await conn.execute(
        "SELECT ascent_m, descent_m, length_m FROM graph.edges WHERE way_id = %s", (way_id,)
    )
    row = await cur.fetchone()
    assert row is not None
    return row


async def test_an_even_slope_scores_its_grade(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_heights(admin_conn, grade(0.05))
    await add_road(admin_conn, EAST, (101, 1, 5), (102, 49, 5))

    await run(mapper_pool, enricher_pool)

    ascent_m, descent_m, length_m = await climb(admin_conn, EAST)
    assert await hills(admin_conn, EAST) == pytest.approx(0.05 / HILLS.full_grade, rel=0.02)
    assert ascent_m == pytest.approx(0.05 * length_m, rel=0.02)
    assert descent_m == 0


async def test_a_way_drawn_downhill_drops(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_heights(admin_conn, grade(0.05))
    await add_road(admin_conn, EAST, (102, 49, 5), (101, 1, 5))

    await run(mapper_pool, enricher_pool)

    ascent_m, descent_m, length_m = await climb(admin_conn, EAST)
    assert ascent_m == 0
    assert descent_m == pytest.approx(0.05 * length_m, rel=0.02)


async def test_flat_ground_and_small_noise_score_nothing(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_road(admin_conn, EAST, (101, 1, 5), (102, 49, 5))
    for heights in ("10", "10 + [rast.x]::int % 2"):
        await add_heights(admin_conn, heights)

        await run(mapper_pool, enricher_pool)

        assert await hills(admin_conn, EAST) == pytest.approx(0, abs=0.02)


async def test_going_up_and_down_again_scores_as_going_up_as_far(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    # A ridge at 18.025, the middle of the road, rising and falling 5 %.
    await add_heights(admin_conn, f"100 - abs([rast.x] - 150) * {0.05 * COLUMN_M}")
    await add_road(admin_conn, EAST, (101, 1, 5), (102, 49, 5))

    await run(mapper_pool, enricher_pool)

    # Smoothing over 60 m rounds off the top: a few metres of the 136 climbed and dropped.
    ascent_m, descent_m, length_m = await climb(admin_conn, EAST)
    assert await hills(admin_conn, EAST) == pytest.approx(0.05 / HILLS.full_grade, rel=0.05)
    assert ascent_m == pytest.approx(0.025 * length_m, rel=0.05)
    assert descent_m == pytest.approx(ascent_m, rel=0.05)


async def test_a_bridge_counts_only_its_ends(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    # A valley under the middle of the bridge, as the height model sees the river below it.
    await add_heights(admin_conn, f"abs([rast.x] - 150) * {0.05 * COLUMN_M}")
    await add_line(
        admin_conn, EAST, [(101, 1, 5), (102, 49, 5)], {"highway": "path", "bridge": "yes"}
    )

    await run(mapper_pool, enricher_pool)

    ascent_m, descent_m, _ = await climb(admin_conn, EAST)
    assert await hills(admin_conn, EAST) == pytest.approx(0, abs=0.02)
    assert ascent_m == pytest.approx(0, abs=1)
    assert descent_m == pytest.approx(0, abs=1)


async def test_a_long_gentle_hill_in_short_edges_still_counts(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    # Each edge is one step, 57 m, and rises 1.1 m: less than the threshold.
    await add_heights(admin_conn, grade(0.02))
    for step in range(10):
        await add_road(admin_conn, 200 + step, (300 + step, 1 + step, 5), (301 + step, 2 + step, 5))

    await run(mapper_pool, enricher_pool)

    edge_scores = await scores(admin_conn)
    for step in range(10):
        ascent_m, _, length_m = await climb(admin_conn, 200 + step)
        assert edge_scores[200 + step]["hills"] == pytest.approx(0.02 / HILLS.full_grade, rel=0.05)
        assert ascent_m == pytest.approx(0.02 * length_m, rel=0.05)


async def test_a_ferry_scores_nothing(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_heights(admin_conn, grade(0.05))
    await add_line(admin_conn, EAST, [(101, 1, 5), (102, 49, 5)], {"route": "ferry"})

    await run(mapper_pool, enricher_pool)

    assert await hills(admin_conn, EAST) == 0
    assert (await climb(admin_conn, EAST))[:2] == (0, 0)


async def test_heights_arriving_after_the_edge_was_scored_rescore_it(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_road(admin_conn, EAST, (101, 1, 5), (102, 49, 5))
    await run(mapper_pool, enricher_pool)
    # Not known, rather than flat.
    assert "hills" not in (await scores(admin_conn))[EAST]
    assert (await climb(admin_conn, EAST))[:2] == (None, None)

    await add_heights(admin_conn, grade(0.05))
    result = await enrich_pending(enricher_pool.connection)

    assert sum(b.elevation_tiles_claimed for b in result.batches) == 1
    ascent_m, _, length_m = await climb(admin_conn, EAST)
    assert await hills(admin_conn, EAST) == pytest.approx(0.05 / HILLS.full_grade, rel=0.02)
    assert ascent_m == pytest.approx(0.05 * length_m, rel=0.02)


async def test_heights_arriving_beside_an_edge_rescore_it(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    # A road starting 30 m east of TILE, so its box misses the tile, but the smoothing reaches
    # into it.
    metres_per_degree = 111_320 * math.cos(math.radians(ORIGIN_LAT))
    start_m = (TILE.bounds.east - ORIGIN_LON) * metres_per_degree + 30
    await add_node_m(admin_conn, 101, start_m, 0.005 * 110_574)
    await add_node_m(admin_conn, 102, start_m + 100, 0.005 * 110_574)
    await add_way(admin_conn, EAST, [101, 102], {"highway": "path"})
    await run(mapper_pool, enricher_pool)
    assert (await climb(admin_conn, EAST))[:2] == (None, None)

    await add_heights(admin_conn, grade(0.05))
    await enrich_pending(enricher_pool.connection)

    ascent_m, _, length_m = await climb(admin_conn, EAST)
    assert ascent_m == pytest.approx(0.05 * length_m, rel=0.1)


@pytest.mark.parametrize(
    ("heights", "ascent_m", "descent_m"),
    [
        ([0, 1, 0, 1, 0], 0, 0),
        ([0, 2, 4], 4, 0),
        ([4, 2, 0], 0, 4),
        ([0, 5, 0], 5, 5),
        ([0, 1, 2, 3], 2, 0),
        ([0, None, 3], 3, 0),
        ([7], 0, 0),
    ],
    ids=[
        "noise",
        "climb",
        "drop",
        "up and down",
        "rest lost at the end",
        "unknown skipped",
        "one",
    ],
)
async def test_climb_counts_steps_of_the_threshold_or_more(
    admin_conn: Conn, heights: list[float | None], ascent_m: float, descent_m: float
) -> None:
    cur = await admin_conn.execute("SELECT * FROM enrich.climb(%s::float8[], 1.5)", (heights,))

    assert await cur.fetchone() == (ascent_m, descent_m)
