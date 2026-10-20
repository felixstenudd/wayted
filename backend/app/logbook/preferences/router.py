"""
HTTP endpoints for the signed-in user's default preference weights
"""

from fastapi import APIRouter

from app.auth.dependencies import UserId
from app.dependencies import Conn

from . import service
from .schemas import PreferencesIn, PreferencesOut

router = APIRouter(prefix="/preferences")


@router.get("")
async def get_preferences(user_id: UserId, db_conn: Conn) -> PreferencesOut:
    """The weights the planner starts from. Attributes left out are "don't mind"."""
    return await service.get_preferences(user_id, db_conn)


@router.put("")
async def save_preferences(user_id: UserId, body: PreferencesIn, db_conn: Conn) -> PreferencesOut:
    """Replace the default weights."""
    return await service.save_preferences(user_id, body.weights, db_conn)
