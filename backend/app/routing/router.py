"""
HTTP endpoints for generating routes
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from app.auth.dependencies import UserId
from app.dependencies import Conn
from app.geojson import LineString

from . import service
from .attributes import ROUTE_ATTRIBUTES
from .schemas import (
    AttributeOut,
    NoRouteOut,
    PlannedRouteOut,
    PreparingOut,
    RoutePropertiesOut,
    RouteRequestIn,
)

router = APIRouter(prefix="/routing", tags=["routing"])


@router.get("/test")
def test() -> dict[str, str]:
    return {"message": "Hello from routing"}


@router.get("/attributes")
def attributes(_: UserId) -> list[AttributeOut]:
    return [AttributeOut(key=a.key, group=a.group, scored=a.scored) for a in ROUTE_ATTRIBUTES]


def _query(request: RouteRequestIn) -> service.RouteQuery:
    finish = request.finish
    return service.RouteQuery(
        activity=request.activity,
        start=service.Coordinate(lon=request.start.lon, lat=request.start.lat),
        finish=service.Coordinate(lon=finish.lon, lat=finish.lat) if finish else None,
        target_m=request.target_distance_m,
        weights=request.preferences,
    )


@router.post(
    "/routes",
    response_model=PlannedRouteOut,
    responses={
        status.HTTP_202_ACCEPTED: {"model": PreparingOut},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": NoRouteOut,
            "description": "No route between the points, or the request is invalid",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Planning took too long"},
    },
)
async def routes(
    _: UserId, request: RouteRequestIn, db_conn: Conn
) -> PlannedRouteOut | JSONResponse:
    """
    Plan a route. Answers 202 while the map data around it is downloaded and scored; the
    client asks again until it gets the route.
    """
    query = _query(request)
    # Commit before planning: the worker only sees the queued tiles once they are committed.
    async with db_conn.transaction():
        ready = await service.prepare(db_conn, query)
    if not ready:
        return JSONResponse(PreparingOut().model_dump(), status.HTTP_202_ACCEPTED)
    try:
        route = await service.plan(db_conn, query)
    except service.NoRoute as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, e.reason) from None
    except service.PlanningTimeout as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from None
    return PlannedRouteOut(
        geometry=LineString(**route.geometry),
        properties=RoutePropertiesOut(
            length_m=route.length_m,
            scores=route.scores,
            reused_m=route.reused_m,
            warnings=route.warnings,
        ),
    )
