import psycopg
import pytest

from app.enrichment import enrich_pending, queries
from app.graph import map_pending

from ..graph.raw_data import Conn, add_node
from .area_data import Pool, add_road, add_square, areas, feature_ways, run, scores

pytestmark = pytest.mark.db

PARK = {"leisure": "park"}


async def queue_sizes(conn: Conn) -> tuple[int, int, int, int]:
    cur = await conn.execute(
        """
        SELECT (SELECT count(*) FROM enrich.pending_ways),
               (SELECT count(*) FROM enrich.pending_relations),
               (SELECT count(*) FROM enrich.pending_nodes),
               (SELECT count(*) FROM graph.pending_edges)
        """
    )
    row = await cur.fetchone()
    assert row is not None
    return row[0], row[1], row[2], row[3]


async def test_mapper_change_is_scored_again(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square(admin_conn, 101, 1, (0, 0, 10, 10), PARK)
    await add_road(admin_conn, 200, (201, 3, 5), (202, 7, 5))
    await run(mapper_pool, enricher_pool)

    # Out of the park, so the mapper resets the score and the enricher must change it.
    await add_node(admin_conn, 202, 30, 5)
    await map_pending(mapper_pool.connection)
    assert (await scores(admin_conn))[200] == {}
    await enrich_pending(enricher_pool.connection)

    green = (await scores(admin_conn))[200]["green"]
    assert 0 < green < 1


async def test_enriching_again_with_nothing_queued_changes_nothing(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square(admin_conn, 101, 1, (0, 0, 10, 10), PARK)
    await add_road(admin_conn, 200, (201, 3, 5), (202, 7, 5))
    await run(mapper_pool, enricher_pool)
    before = (await scores(admin_conn), await areas(admin_conn), await feature_ways(admin_conn))

    result = await enrich_pending(enricher_pool.connection)

    assert result.batches == ()
    assert (
        await scores(admin_conn),
        await areas(admin_conn),
        await feature_ways(admin_conn),
    ) == before


async def test_batches_of_one_give_the_same_result(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square(admin_conn, 101, 1, (0, 0, 10, 10), PARK)
    await add_square(admin_conn, 102, 5, (20, 0, 30, 10), PARK)
    await add_road(admin_conn, 200, (201, 3, 5), (202, 25, 5))
    await add_road(admin_conn, 300, (301, 0, 3), (302, 0, 7))
    await map_pending(mapper_pool.connection)

    await enrich_pending(enricher_pool.connection, batch_size=1)
    small = await scores(admin_conn)
    await admin_conn.execute("UPDATE graph.edges SET scores = '{}'")
    await admin_conn.execute("INSERT INTO graph.pending_edges (edge_id) SELECT id FROM graph.edges")
    await enrich_pending(enricher_pool.connection)

    def green(by_way: dict[int, dict[str, float]]) -> dict[int, float]:
        return {way_id: s["green"] for way_id, s in by_way.items()}

    assert green(await scores(admin_conn)) == pytest.approx(green(small))


async def test_failed_batch_leaves_everything_untouched(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    await add_square(admin_conn, 101, 1, (0, 0, 10, 10), PARK)
    await add_road(admin_conn, 200, (201, 3, 5), (202, 7, 5))
    await map_pending(mapper_pool.connection)
    queued = await queue_sizes(admin_conn)
    # After the features are written, before any score.
    monkeypatch.setattr(queries, "CLAIM_EDGES", "SELECT 1 / 0")

    with pytest.raises(psycopg.errors.DivisionByZero):
        await enrich_pending(enricher_pool.connection)

    assert await areas(admin_conn) == []
    assert await feature_ways(admin_conn) == set()
    assert (await scores(admin_conn))[200] == {}
    assert await queue_sizes(admin_conn) == queued
