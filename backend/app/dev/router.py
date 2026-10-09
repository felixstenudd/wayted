"""HTTP endpoints of the dev API."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import Conn
from app.dev.schemas import (
    AreaRequestIn,
    AreaRequestOut,
    BoundsOut,
    EdgeOut,
    ErrorOut,
    Feature,
    FeatureCollection,
    FetchedTileOut,
    GraphOut,
    LineString,
    Point,
    Polygon,
    QueuedTileOut,
    VertexOut,
)
from app.graph.area import AreaTooLarge, graph_in_bounds
from app.sources.queue import queued_tiles, request_area
from app.sources.registry import fetched_tiles
from app.sources.tiles import Bounds, Tile, bounds_for_circle

MAX_EDGES = 25_000

router = APIRouter()

Lon = Annotated[float, Query(ge=-180, le=180)]
Lat = Annotated[float, Query(ge=-90, le=90)]


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


@router.get("/graph", responses={status.HTTP_400_BAD_REQUEST: {"model": ErrorOut}})
async def graph(db_conn: Conn, west: Lon, south: Lat, east: Lon, north: Lat) -> GraphOut:
    """The edges that intersect the box, and the vertices at their ends."""
    bounds = Bounds(west=west, south=south, east=east, north=north)
    try:
        area = await graph_in_bounds(db_conn, bounds, MAX_EDGES)
    except AreaTooLarge as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{e} Zoom in and try again.") from None
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from None
    return GraphOut(
        edges=FeatureCollection(
            features=[
                Feature(
                    geometry=LineString(**edge.geometry),
                    properties=EdgeOut(
                        id=edge.id,
                        way_id=edge.way_id,
                        source=edge.source,
                        target=edge.target,
                        length_m=edge.length_m,
                        forward=edge.forward,
                        backward=edge.backward,
                        scores=edge.scores,
                        tags=edge.tags,
                    ),
                )
                for edge in area.edges
            ]
        ),
        vertices=FeatureCollection(
            features=[
                Feature(geometry=Point(**vertex.geometry), properties=VertexOut(id=vertex.id))
                for vertex in area.vertices
            ]
        ),
    )


@router.post("/requests", status_code=status.HTTP_202_ACCEPTED)
async def request_circle(body: AreaRequestIn, db_conn: Conn) -> AreaRequestOut:
    """Queue the tiles around a circle for the worker. Returns how many rows this call queued."""
    bounds = bounds_for_circle(body.lat, body.lon, body.radius_m)
    # Commit before answering: the connection itself is released after the response is sent.
    async with db_conn.transaction():
        queued = await request_area(db_conn, bounds, body.refetch)
    return AreaRequestOut(queued=queued, bounds=BoundsOut(**asdict(bounds)))
