"""
Generates routes of a target length from a start point, back to it or to a finish, weighted by the
user's preferences. The planning runs in the database (routing.plan_route in
db/init/60_routing.sql, on pgRouting); this package only makes sure the map data is there and
calls it.
"""

from .router import router

__all__ = ["router"]  # defines public API for module
