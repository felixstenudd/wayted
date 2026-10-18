import os
from collections.abc import AsyncIterator

import pytest
from psycopg import AsyncConnection
from psycopg.conninfo import make_conninfo
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

TEST_DATABASE_URL = os.environ.get("WAYTED_TEST_DATABASE_URL")
DOWNLOADER_PASSWORD = os.environ.get("WAYTED_TEST_DOWNLOADER_PASSWORD", "test")
MAPPER_PASSWORD = os.environ.get("WAYTED_TEST_MAPPER_PASSWORD", "test")
ENRICHER_PASSWORD = os.environ.get("WAYTED_TEST_ENRICHER_PASSWORD", "test")
API_PASSWORD = os.environ.get("WAYTED_TEST_API_PASSWORD", "test")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if TEST_DATABASE_URL:
        return
    skip = pytest.mark.skip(reason="set WAYTED_TEST_DATABASE_URL to run database tests")
    for item in items:
        # keywords would also match a folder named db, so check for the marker itself.
        if item.get_closest_marker("db"):
            item.add_marker(skip)


@pytest.fixture
async def admin_conn() -> AsyncIterator[AsyncConnection[TupleRow]]:
    """Superuser connection for setup and assertions. Empties raw, graph and enrich first."""
    assert TEST_DATABASE_URL
    conn = await AsyncConnection.connect(TEST_DATABASE_URL, autocommit=True)
    await conn.execute(
        """
        TRUNCATE raw.fetched_tiles, raw.pending_tiles,
            raw.osm_nodes, raw.osm_ways, raw.osm_relations,
            graph.ways, graph.vertices, graph.edges,
            graph.pending_ways, graph.pending_nodes, graph.pending_edges,
            enrich.areas, enrich.feature_ways,
            enrich.pending_ways, enrich.pending_relations, enrich.pending_nodes
        RESTART IDENTITY
        """
    )
    yield conn
    await conn.close()


@pytest.fixture
async def downloader_pool(
    admin_conn: AsyncConnection[TupleRow],
) -> AsyncIterator[AsyncConnectionPool[AsyncConnection[TupleRow]]]:
    """Pool logged in as wayted_downloader, so tests go through the real grants."""
    assert TEST_DATABASE_URL
    conninfo = make_conninfo(
        TEST_DATABASE_URL, user="wayted_downloader", password=DOWNLOADER_PASSWORD
    )
    pool = AsyncConnectionPool(conninfo, open=False)
    await pool.open()
    yield pool
    await pool.close()


@pytest.fixture
async def mapper_pool(
    admin_conn: AsyncConnection[TupleRow],
) -> AsyncIterator[AsyncConnectionPool[AsyncConnection[TupleRow]]]:
    """Pool logged in as wayted_mapper, so tests go through the real grants."""
    assert TEST_DATABASE_URL
    conninfo = make_conninfo(TEST_DATABASE_URL, user="wayted_mapper", password=MAPPER_PASSWORD)
    pool = AsyncConnectionPool(conninfo, open=False)
    await pool.open()
    yield pool
    await pool.close()


@pytest.fixture
async def enricher_pool(
    admin_conn: AsyncConnection[TupleRow],
) -> AsyncIterator[AsyncConnectionPool[AsyncConnection[TupleRow]]]:
    """Pool logged in as wayted_enricher, so tests go through the real grants."""
    assert TEST_DATABASE_URL
    conninfo = make_conninfo(TEST_DATABASE_URL, user="wayted_enricher", password=ENRICHER_PASSWORD)
    pool = AsyncConnectionPool(conninfo, open=False)
    await pool.open()
    yield pool
    await pool.close()


@pytest.fixture
async def api_pool(
    admin_conn: AsyncConnection[TupleRow],
) -> AsyncIterator[AsyncConnectionPool[AsyncConnection[TupleRow]]]:
    """Pool logged in as wayted_api, so tests go through the real grants."""
    assert TEST_DATABASE_URL
    conninfo = make_conninfo(TEST_DATABASE_URL, user="wayted_api", password=API_PASSWORD)
    pool = AsyncConnectionPool(conninfo, open=False)
    await pool.open()
    yield pool
    await pool.close()


@pytest.fixture
async def listener(
    admin_conn: AsyncConnection[TupleRow],
) -> AsyncIterator[AsyncConnection[TupleRow]]:
    """Connection of its own as wayted_downloader, for LISTEN."""
    assert TEST_DATABASE_URL
    conninfo = make_conninfo(
        TEST_DATABASE_URL, user="wayted_downloader", password=DOWNLOADER_PASSWORD
    )
    conn = await AsyncConnection.connect(conninfo, autocommit=True)
    yield conn
    await conn.close()
