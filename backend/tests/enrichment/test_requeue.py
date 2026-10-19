import pytest

from app.enrichment import enrich_pending
from app.enrichment.requeue import requeue

from ..graph.raw_data import Conn, add_way
from .area_data import Pool, add_road, add_square, areas, run

pytestmark = pytest.mark.db

PARK = {"leisure": "park"}


async def counts(conn: Conn) -> tuple[int, int, int]:
    cur = await conn.execute(
        """
        SELECT (SELECT count(*) FROM graph.pending_edges),
               (SELECT count(*) FROM enrich.pending_ways),
               (SELECT count(*) FROM enrich.pending_relations)
        """
    )
    row = await cur.fetchone()
    assert row is not None
    return row[0], row[1], row[2]


async def test_requeue_queues_every_edge(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square(admin_conn, 101, 1, (0, 0, 10, 10), PARK)
    await add_road(admin_conn, 200, (201, 3, 5), (202, 7, 5))
    await add_road(admin_conn, 300, (301, 0, 3), (302, 0, 7))
    await run(mapper_pool, enricher_pool)

    async with enricher_pool.connection() as conn:
        assert await requeue(conn, features=False) == (2, 0)

    assert await counts(admin_conn) == (2, 0, 0)


async def test_requeue_features_queues_matching_elements(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square(admin_conn, 101, 1, (0, 0, 10, 10), PARK)
    await add_road(admin_conn, 200, (201, 3, 5), (202, 7, 5))
    await run(mapper_pool, enricher_pool)

    async with enricher_pool.connection() as conn:
        assert await requeue(conn, features=True) == (1, 1)

    assert await counts(admin_conn) == (1, 1, 0)


async def test_requeue_features_includes_features_that_no_longer_match(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_square(admin_conn, 101, 1, (0, 0, 10, 10), PARK)
    await run(mapper_pool, enricher_pool)
    # As if the layer's pattern had been narrowed: the area exists, its raw way no longer matches.
    await admin_conn.execute("ALTER TABLE raw.osm_ways DISABLE TRIGGER USER")
    await add_way(admin_conn, 101, [1, 2, 3, 4, 1], {"leisure": "garden"})
    await admin_conn.execute("ALTER TABLE raw.osm_ways ENABLE TRIGGER USER")

    async with enricher_pool.connection() as conn:
        assert await requeue(conn, features=True) == (0, 1)
    await enrich_pending(enricher_pool.connection)

    assert await areas(admin_conn) == []
