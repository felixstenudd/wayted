"""
HTTP endpoints for generating routes
"""

from fastapi import APIRouter, HTTPException, status

from app.auth.dependencies import UserId

from .attributes import ROUTE_ATTRIBUTES
from .schemas import AttributeOut, RouteRequestIn

router = APIRouter(prefix="/routing", tags=["routing"])


@router.get("/test")
def test() -> dict[str, str]:
    return {"message": "Hello from routing"}


@router.get("/attributes")
def attributes(_: UserId) -> list[AttributeOut]:
    return [AttributeOut(key=a.key, group=a.group, scored=a.scored) for a in ROUTE_ATTRIBUTES]


@router.post(
    "/routes", responses={status.HTTP_501_NOT_IMPLEMENTED: {"description": "Not available yet"}}
)
def routes(_: UserId, request: RouteRequestIn) -> None:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Route generation is not available yet.")
