import httpx
import pytest

from app.sources import DownloadError, DownloadStatus
from app.sources.elevation import Cell, ElevationDownloader, cells_for_bounds
from app.sources.elevation.copernicus import DEM_URL
from app.sources.tiles import Bounds

TIFF = b"II*\x00rest of the file"


def client_answering(responses: dict[str, httpx.Response], seen: list[str]) -> httpx.AsyncClient:
    """Answers each URL from responses, and 404 for any other."""

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return responses.get(str(request.url), httpx.Response(404))

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_cells_are_named_by_their_south_west_corner() -> None:
    assert Cell(63, 20).name == "Copernicus_DSM_COG_10_N63_00_E020_00_DEM"
    assert Cell(-34, -71).name == "Copernicus_DSM_COG_10_S34_00_W071_00_DEM"
    assert Cell(0, 0).url == (
        f"{DEM_URL}/Copernicus_DSM_COG_10_N00_00_E000_00_DEM/"
        "Copernicus_DSM_COG_10_N00_00_E000_00_DEM.tif"
    )


@pytest.mark.parametrize(
    ("bounds", "cells"),
    [
        (Bounds(west=20.2, south=63.8, east=20.3, north=63.9), [Cell(63, 20)]),
        (
            Bounds(west=20.9, south=63.9, east=21.1, north=64.1),
            [Cell(63, 20), Cell(63, 21), Cell(64, 20), Cell(64, 21)],
        ),
        # An edge on a whole degree reaches no further.
        (Bounds(west=20.0, south=63.0, east=21.0, north=64.0), [Cell(63, 20)]),
        (Bounds(west=-0.1, south=-0.1, east=-0.05, north=-0.05), [Cell(-1, -1)]),
    ],
    ids=["inside one", "across corners", "on whole degrees", "south-west of zero"],
)
def test_bounds_reach_into_the_cells_they_overlap(bounds: Bounds, cells: list[Cell]) -> None:
    assert cells_for_bounds(bounds) == cells


async def test_fetch_downloads_every_cell_and_leaves_out_open_sea() -> None:
    seen: list[str] = []
    land = {Cell(63, 20).url: httpx.Response(200, content=TIFF)}
    async with client_answering(land, seen) as client:
        data = await ElevationDownloader(client).fetch(
            Bounds(west=20.9, south=63.5, east=21.1, north=63.6)
        )

    assert sorted(seen) == sorted([Cell(63, 20).url, Cell(63, 21).url])
    assert data.files == (TIFF,)


async def test_files_are_kept_for_the_next_rectangles() -> None:
    seen: list[str] = []
    land = {Cell(63, 20).url: httpx.Response(200, content=TIFF)}
    async with client_answering(land, seen) as client:
        downloader = ElevationDownloader(client, cached_files=1)
        for west in (20.1, 20.2, 21.1, 20.3):
            await downloader.fetch(Bounds(west=west, south=63.5, east=west + 0.05, north=63.6))

    # The sea cell to the east pushed the first file out, so it was fetched again.
    assert seen == [Cell(63, 20).url, Cell(63, 21).url, Cell(63, 20).url]


@pytest.mark.parametrize(
    ("response", "status"),
    [
        (httpx.Response(429), DownloadStatus.RATE_LIMITED),
        (httpx.Response(503), DownloadStatus.SOURCE_ERROR),
        (httpx.Response(403), DownloadStatus.INVALID_RESPONSE),
        (httpx.Response(200, content=b"<html>maintenance</html>"), DownloadStatus.INVALID_RESPONSE),
    ],
    ids=["rate limited", "server error", "refused", "not a tiff"],
)
async def test_failed_downloads_are_classified(
    response: httpx.Response, status: DownloadStatus
) -> None:
    async with client_answering({Cell(63, 20).url: response}, []) as client:
        with pytest.raises(DownloadError) as caught:
            await ElevationDownloader(client).fetch(
                Bounds(west=20.2, south=63.8, east=20.3, north=63.9)
            )

    assert caught.value.status is status
