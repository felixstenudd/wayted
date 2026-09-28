"""
Creates an AsyncConnectionPool per database role
"""

<<<<<<< HEAD
from .db import close_pools, connection, open_pool

__all__ = ["open_pool", "close_pools", "connection"]
=======
from .pool import api_pool, downloader_pool

__all__ = ["api_pool", "downloader_pool"]
>>>>>>> origin/main
