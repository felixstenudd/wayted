"""
HTTP endpoints for users' saved routes and their feedback
"""

from fastapi import APIRouter

from . import routes

router = APIRouter(prefix="/logbook", tags=["logbook"])
router.include_router(routes.router)
