"""
HTTP endpoints for generating routes
"""

from fastapi import APIRouter

router = APIRouter(prefix="/routing", tags=["routing"])


@router.get("/test")
def test():
    return {"message": "Hello from routing"}
