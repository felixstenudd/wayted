"""
Creates an AsyncConnectionPool per database role
"""

from .db import close_pools, connection, open_pool

__all__ = ["close_pools", "connection", "open_pool"]
