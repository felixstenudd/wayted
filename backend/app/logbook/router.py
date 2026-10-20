"""
HTTP endpoints for users' saved routes and their feedback
"""

from fastapi import APIRouter

from . import preferences, route_reviews, routes

router = APIRouter(prefix="/logbook", tags=["logbook"])
router.include_router(routes.router)
router.include_router(route_reviews.router)
router.include_router(preferences.router)
