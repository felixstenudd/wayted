"""
The Copernicus DEM GLO-30 height model: one GeoTIFF per 1 by 1 degree cell, public on AWS.
Heights are of the surface the satellite saw, trees and buildings included.
"""

import os
from dataclasses import dataclass
from math import ceil, floor

import httpx

from ..downloader import DownloadError, DownloadStatus
from ..tiles import Bounds

DEM_URL = os.environ.get("COPERNICUS_DEM_URL", "https://copernicus-dem-30m.s3.amazonaws.com")
USER_AGENT = "wayted/0.1"
# A file is a few MB.
HTTP_TIMEOUT_S = 60

# Every TIFF starts with its byte order and the number 42.
TIFF_MAGIC = (b"II*\x00", b"MM\x00*")


@dataclass(frozen=True, slots=True)
class Cell:
    """The 1 by 1 degree cell whose south-west corner is (lat, lon)."""

    lat: int
    lon: int

    @property
    def name(self) -> str:
        north_south = f"{'N' if self.lat >= 0 else 'S'}{abs(self.lat):02d}"
        east_west = f"{'E' if self.lon >= 0 else 'W'}{abs(self.lon):03d}"
        return f"Copernicus_DSM_COG_10_{north_south}_00_{east_west}_00_DEM"

    @property
    def url(self) -> str:
        return f"{DEM_URL}/{self.name}/{self.name}.tif"


def cells_for_bounds(bounds: Bounds) -> list[Cell]:
    """The cells bounds reaches into, south-west first. An edge on a whole degree reaches no
    further."""
    lats = range(floor(bounds.south), max(ceil(bounds.north), floor(bounds.south) + 1))
    lons = range(floor(bounds.west), max(ceil(bounds.east), floor(bounds.west) + 1))
    return [Cell(lat, lon) for lat in lats for lon in lons]


def new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT_S)


async def fetch_cell(client: httpx.AsyncClient, cell: Cell) -> bytes | None:
    """The cell's GeoTIFF, or None where there is none: open sea. Raises DownloadError."""
    response = await client.get(cell.url)
    if response.status_code == 404:
        return None
    if response.status_code == 429:
        raise DownloadError(DownloadStatus.RATE_LIMITED, "The DEM host is rate limiting us (429).")
    if 400 <= response.status_code < 500:
        raise DownloadError(
            DownloadStatus.INVALID_RESPONSE,
            f"The DEM host refused {cell.name} ({response.status_code}).",
        )
    if not response.is_success:
        raise DownloadError(
            DownloadStatus.SOURCE_ERROR, f"The DEM host answered {response.status_code}."
        )
    if not response.content.startswith(TIFF_MAGIC):
        raise DownloadError(DownloadStatus.INVALID_RESPONSE, f"{cell.name} is not a TIFF.")
    return response.content
