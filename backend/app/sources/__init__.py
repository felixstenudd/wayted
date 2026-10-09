"""
Fetches and stores raw data per tile. Keeps a tile registry that records
what has been fetched and when, so tiles are only fetched once and can
be refreshed later.
"""

from .downloader import Downloader, DownloadError, DownloadStatus, RectangleResult
from .queue import request_area
from .runner import download_tiles
from .tiles import Bounds, Tile, TileRect, bounds_for_tiles, tiles_for_bounds

__all__ = [
    "Bounds",
    "DownloadError",
    "DownloadStatus",
    "Downloader",
    "RectangleResult",
    "Tile",
    "TileRect",
    "bounds_for_tiles",
    "download_tiles",
    "request_area",
    "tiles_for_bounds",
]
