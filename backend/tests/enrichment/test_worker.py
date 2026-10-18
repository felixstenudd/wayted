import asyncio
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress

import pytest

from app.enrichment import worker
from app.graph import map_pending

from ..graph.raw_data import Conn
from .area_data import Pool, add_road, add_square, scores

pytestmark = pytest.mark.db

PARK = {"leisure": "park"}


async def eventually(check: Callable[[], Awaitable[bool]], timeout_s: float = 10) -> None:
    deadline = time.monotonic() + timeout_s
    while not await check():
        assert time.monotonic() < deadline, "condition was not met in time"
        await asyncio.sleep(0.05)


async def test_serve_drains_the_queue_and_wakes_for_new_work(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool, listener: Conn
) -> None:
    # Queued while the enricher was down.
    await add_square(admin_conn, 101, 1, (0, 0, 10, 10), PARK)
    await add_road(admin_conn, 200, (201, 3, 5), (202, 7, 5))
    await map_pending(mapper_pool.connection)

    async def scored(way_id: int) -> bool:
        return "green" in (await scores(admin_conn)).get(way_id, {})

    serving = asyncio.create_task(worker.serve(enricher_pool.connection, listener))
    try:
        await eventually(lambda: scored(200))
        await add_road(admin_conn, 300, (301, 0, 3), (302, 0, 7))
        await map_pending(mapper_pool.connection)
        await eventually(lambda: scored(300))
    finally:
        serving.cancel()
        with suppress(asyncio.CancelledError):
            await serving
