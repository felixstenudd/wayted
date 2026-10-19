"""Background process that scores edges whenever the mapper or a download queues work."""

import asyncio
import logging
from functools import partial

import psycopg
from psycopg import AsyncConnection
from psycopg.conninfo import make_conninfo
from psycopg.rows import TupleRow

from app import db
from app.db import Connect

from .enricher import EnrichResult, enrich_pending

log = logging.getLogger("wayted.enricher")

NOTIFY_CHANNEL = "pending_enrichment"


async def serve(connect: Connect, listener: AsyncConnection[TupleRow]) -> None:
    """Run until cancelled. listener is an autocommit connection used for nothing else."""
    # Listen before the first run: work queued during a run is buffered and ends the next wait.
    await listener.execute(f"LISTEN {NOTIFY_CHANNEL}")
    log.info("enricher started")
    while True:
        try:
            _log_run(await enrich_pending(connect))
        except psycopg.Error as e:
            # The queues still hold the work; the next notification retries it.
            log.error("enriching failed: %s", e)
        async for _ in listener.notifies(stop_after=1):
            pass


def _log_run(result: EnrichResult) -> None:
    if not result.batches:
        return
    log.info(
        "enriched: %d features built, %d deleted, %d skipped, %d edges scored",
        sum(b.features_built for b in result.batches),
        sum(b.features_deleted for b in result.batches),
        sum(b.features_skipped for b in result.batches),
        sum(b.edges_scored for b in result.batches),
    )


async def main() -> None:
    # app.config reads the environment on import; here, so the tests can import this module.
    from app.config import ENRICHER_ROLE, ENRICHER_ROLE_PASSWORD

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    await db.open_pool(ENRICHER_ROLE, ENRICHER_ROLE_PASSWORD)
    conninfo = make_conninfo(user=ENRICHER_ROLE, password=ENRICHER_ROLE_PASSWORD)
    try:
        async with await AsyncConnection.connect(conninfo, autocommit=True) as listener:
            await serve(partial(db.connection, ENRICHER_ROLE), listener)
    finally:
        await db.close_pools()


if __name__ == "__main__":
    asyncio.run(main())
