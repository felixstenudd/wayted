"""HTTP endpoints of the dev API."""

from fastapi import APIRouter

from app.dependencies import Conn
from app.dev.schemas import (
    Feature,
    FeatureCollection,
    FetchedTileOut,
    Polygon,
    QueuedTileOut,
)
from app.sources.queue import queued_tiles
from app.sources.registry import fetched_tiles
from app.sources.tiles import Tile

router = APIRouter()


def _outline(tile: Tile) -> Polygon:
    b = tile.bounds
    ring = [(b.west, b.south), (b.east, b.south), (b.east, b.north), (b.west, b.north)]
    return Polygon(type="Polygon", coordinates=[[*ring, ring[0]]])


@router.get("/health")
async def health(db_conn: Conn) -> dict[str, str]:
    await db_conn.execute("SELECT 1")
    return {"status": "ok"}


@router.get("/tiles/fetched")
async def list_fetched_tiles(db_conn: Conn) -> FeatureCollection[Polygon, FetchedTileOut]:
    """Every fetched tile, oldest fetch first. Expired tiles are included."""
    return FeatureCollection(
        features=[
            Feature(
                geometry=_outline(f.tile),
                properties=FetchedTileOut(
                    layer=f.layer,
                    z=f.tile.z,
                    x=f.tile.x,
                    y=f.tile.y,
                    fetched_at=f.fetched_at,
                    expires_at=f.expires_at,
                ),
            )
            for f in await fetched_tiles(db_conn)
        ]
    )


@router.get("/tiles/queued")
async def list_queued_tiles(db_conn: Conn) -> FeatureCollection[Polygon, QueuedTileOut]:
    """Every tile waiting, being fetched or failed, oldest request first."""
    return FeatureCollection(
        features=[
            Feature(
                geometry=_outline(q.tile),
                properties=QueuedTileOut(
                    layer=q.layer,
                    z=q.tile.z,
                    x=q.tile.x,
                    y=q.tile.y,
                    requested_at=q.requested_at,
                    status=q.status,
                    attempts=q.attempts,
                    next_attempt_at=q.next_attempt_at,
                    last_status=q.last_status,
                    last_message=q.last_message,
                ),
            )
            for q in await queued_tiles(db_conn)
        ]
    )
