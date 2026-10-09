"""
HTTP endpoints for users' saved routes and their feedback
"""

from fastapi import APIRouter

router = APIRouter(prefix="/logbook", tags=["logbook"])


@router.get("/test")
def test() -> dict[str, str]:
    return {"message": "Hello from logbook"}
