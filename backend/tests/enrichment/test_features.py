import pytest

from app.enrichment import LAYERS
from app.sources.osm import LAYERS as DOWNLOADED_LAYERS

from ..graph.raw_data import ORIGIN_LAT, ORIGIN_LON, STEP, Conn, add_node, add_way
from .area_data import Pool, add_relation, add_square, area_is, areas, feature_ways, grid_wkt, run

pytestmark = pytest.mark.db

PARK = {"leisure": "park"}
MULTIPOLYGON_PARK = {"leisure": "park", "type": "multipolygon"}


async def test_closed_park_way_becomes_an_area(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square(admin_conn, 101, 1, (0, 0, 10, 10), PARK)

    result = await run(mapper_pool, enricher_pool)

    assert await areas(admin_conn) == [("way", 101)]
    assert await area_is(admin_conn, "way", 101, grid_wkt((0, 0, 10, 10)))
    assert sum(b.features_built for b in result.batches) == 1


async def test_multipolygon_with_a_hole(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square(admin_conn, 20, 1, (0, 0, 10, 10), {})
    await add_square(admin_conn, 22, 5, (4, 4, 6, 6), {})
    # Roles swapped on purpose: rings are nested by geometry, not by role.
    await add_relation(admin_conn, 30, [(20, "inner"), (22, "outer")], MULTIPOLYGON_PARK)

    await run(mapper_pool, enricher_pool)

    assert await areas(admin_conn) == [("relation", 30)]
    assert await area_is(admin_conn, "relation", 30, grid_wkt((0, 0, 10, 10), (4, 4, 6, 6)))


async def test_outline_split_over_two_member_ways(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    for node_id, x, y in [(1, 0, 0), (2, 10, 0), (3, 10, 10), (4, 0, 10)]:
        await add_node(admin_conn, node_id, x, y)
    await add_way(admin_conn, 20, [1, 2, 3], {})
    await add_way(admin_conn, 21, [3, 4, 1], {})
    await add_relation(admin_conn, 30, [(20, "outer"), (21, "outer")], MULTIPOLYGON_PARK)

    await run(mapper_pool, enricher_pool)

    assert await area_is(admin_conn, "relation", 30, grid_wkt((0, 0, 10, 10)))
    assert await feature_ways(admin_conn) == {("relation", 30, 20), ("relation", 30, 21)}


async def test_self_crossing_park_way_becomes_an_area(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    # The outline crosses itself at (10, 10), leaving a small loop at that corner.
    for node_id, x, y in [(1, 0, 0), (2, 10, 0), (3, 10, 11), (4, 11, 10), (5, 0, 10)]:
        await add_node(admin_conn, node_id, x, y)
    await add_way(admin_conn, 101, [1, 2, 3, 4, 5, 1], PARK)

    result = await run(mapper_pool, enricher_pool)

    def ring(corners: list[tuple[int, int]]) -> str:
        return ", ".join(f"{ORIGIN_LON + x * STEP} {ORIGIN_LAT + y * STEP}" for x, y in corners)

    square = ring([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
    loop = ring([(10, 10), (10, 11), (11, 10), (10, 10)])
    assert await area_is(admin_conn, "way", 101, f"MULTIPOLYGON((({square})), (({loop})))")
    assert sum(b.features_skipped for b in result.batches) == 0


async def test_member_way_listed_twice_still_builds(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    for node_id, x, y in [(1, 0, 0), (2, 10, 0), (3, 10, 10), (4, 0, 10)]:
        await add_node(admin_conn, node_id, x, y)
    await add_way(admin_conn, 20, [1, 2, 3], {})
    await add_way(admin_conn, 21, [3, 4, 1], {})
    await add_relation(
        admin_conn, 30, [(20, "outer"), (20, "outer"), (21, "outer")], MULTIPOLYGON_PARK
    )

    await run(mapper_pool, enricher_pool)

    assert await area_is(admin_conn, "relation", 30, grid_wkt((0, 0, 10, 10)))


async def test_missing_member_way_is_skipped_until_it_arrives(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    for node_id, x, y in [(1, 0, 0), (2, 10, 0), (3, 10, 10), (4, 0, 10)]:
        await add_node(admin_conn, node_id, x, y)
    await add_way(admin_conn, 20, [1, 2, 3], {})
    await add_relation(admin_conn, 30, [(20, "outer"), (21, "outer")], MULTIPOLYGON_PARK)

    first = await run(mapper_pool, enricher_pool)

    assert await areas(admin_conn) == []
    assert sum(b.features_skipped for b in first.batches) == 1
    assert await feature_ways(admin_conn) == {("relation", 30, 20), ("relation", 30, 21)}

    await add_way(admin_conn, 21, [3, 4, 1], {})
    await run(mapper_pool, enricher_pool)

    assert await areas(admin_conn) == [("relation", 30)]


async def test_open_park_way_is_skipped(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    for node_id, x, y in [(1, 0, 0), (2, 10, 0), (3, 10, 10)]:
        await add_node(admin_conn, node_id, x, y)
    await add_way(admin_conn, 101, [1, 2, 3], PARK)

    result = await run(mapper_pool, enricher_pool)

    assert await areas(admin_conn) == []
    assert sum(b.features_skipped for b in result.batches) == 1


async def test_relation_without_way_members_is_skipped(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_relation(admin_conn, 30, [], MULTIPOLYGON_PARK)

    result = await run(mapper_pool, enricher_pool)

    assert await areas(admin_conn) == []
    assert sum(b.features_skipped for b in result.batches) == 1


async def test_park_tag_removed_deletes_the_area(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square(admin_conn, 101, 1, (0, 0, 10, 10), PARK)
    await run(mapper_pool, enricher_pool)

    await add_way(admin_conn, 101, [1, 2, 3, 4, 1], {"name": "Former park"})
    result = await run(mapper_pool, enricher_pool)

    assert await areas(admin_conn) == []
    assert sum(b.features_deleted for b in result.batches) == 1


async def test_moving_an_outline_node_rebuilds_the_area(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square(admin_conn, 20, 1, (0, 0, 10, 10), {})
    await add_relation(admin_conn, 30, [(20, "outer")], MULTIPOLYGON_PARK)
    await run(mapper_pool, enricher_pool)

    await add_node(admin_conn, 3, 20, 10)
    await run(mapper_pool, enricher_pool)

    corners = [(0, 0), (10, 0), (20, 10), (0, 10), (0, 0)]
    ring = ", ".join(f"{ORIGIN_LON + x * STEP} {ORIGIN_LAT + y * STEP}" for x, y in corners)
    assert await area_is(admin_conn, "relation", 30, f"POLYGON(({ring}))")


@pytest.mark.parametrize(
    "tags",
    [
        {"landuse": "forest"},
        {"natural": "wood"},
        {"natural": "scrub"},
        {"natural": "heath"},
        {"natural": "grassland"},
        {"landuse": "meadow"},
        {"natural": "wetland"},
        {"leisure": "nature_reserve"},
    ],
)
async def test_natural_land_becomes_a_nature_area(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool, tags: dict[str, str]
) -> None:
    await add_square(admin_conn, 101, 1, (0, 0, 10, 10), tags)

    await run(mapper_pool, enricher_pool)

    cur = await admin_conn.execute("SELECT layer, osm_type, osm_id FROM enrich.areas")
    assert await cur.fetchall() == [("nature", "way", 101)]


async def test_every_downloaded_area_layer_is_built_from_the_same_tags() -> None:
    built = {layer.code: layer.match for layer in LAYERS}

    for layer in DOWNLOADED_LAYERS:
        if layer.is_area:
            assert built.get(layer.code) == layer.tags, layer.code
