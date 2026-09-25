"""
HTTP endpoints for handling user accounts
"""

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/test")
def test():
    return {"message": "Hello from auth"}
