"""
Generates routes from a start point, an endpoint, optional via points,
a target distance and user preferences. Builds a per-request cost from
edge attributes, user weigths and feedback, then searches the graph with
pgRouting
"""

from .router import router

__all__ = ["router"]  # defines public API for module
