"""Downloader for terrain heights, from the Copernicus DEM GLO-30."""

from .copernicus import Cell, cells_for_bounds, new_client
from .downloader import LAYER, ElevationData, ElevationDownloader

__all__ = [
    "LAYER",
    "Cell",
    "ElevationData",
    "ElevationDownloader",
    "cells_for_bounds",
    "new_client",
]
