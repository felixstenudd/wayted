"""Building, sending and parsing Overpass API queries."""

import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from ..downloader import DownloadError, DownloadStatus
from ..tiles import Bounds

OVERPASS_URL = os.environ.get("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
# The Overpass usage policy asks clients to identify themselves.
USER_AGENT = "wayted/0.1"
QUERY_TIMEOUT_S = 90
HTTP_TIMEOUT_S = QUERY_TIMEOUT_S + 15

type Coords = list[tuple[float, float]]  # (lon, lat) pairs


@dataclass(frozen=True, slots=True)
class OsmWay:
    id: int
    tags: dict[str, str]
    coords: Coords


@dataclass(frozen=True, slots=True)
class OsmMember:
    role: str
    coords: Coords


@dataclass(frozen=True, slots=True)
class OsmRelation:
    id: int
    tags: dict[str, str]
    members: list[OsmMember]


type OsmElement = OsmWay | OsmRelation


def build_query(selectors: Sequence[str], bounds: Bounds, timeout_s: int = QUERY_TIMEOUT_S) -> str:
    """Return a query for everything matching the selectors inside bounds, with full geometry."""
    # Overpass orders bbox: south, west, north, east.
    bbox = f"({bounds.south},{bounds.west},{bounds.north},{bounds.east})"
    union = "".join(f"{selector}{bbox};" for selector in selectors)
    return f"[out:json][timeout:{timeout_s}];({union});out tags geom;"


def new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=HTTP_TIMEOUT_S,
    )


async def run_query(client: httpx.AsyncClient, query: str) -> list[OsmElement]:
    """Send a query and return its ways and relations. Raises DownloadError on any failure."""
    response = await client.post(OVERPASS_URL, data={"data": query})
    _raise_for_status(response)
    try:
        body = response.json()
    except ValueError as e:
        raise DownloadError(DownloadStatus.INVALID_RESPONSE, "Response is not JSON.") from e
    if not isinstance(body, dict):
        raise DownloadError(DownloadStatus.INVALID_RESPONSE, "Response is not a JSON object.")
    _raise_for_remark(body)
    return _parse_elements(body)


def _raise_for_status(response: httpx.Response) -> None:
    if response.is_success:
        return
    code = response.status_code
    if code == 429:
        raise DownloadError(DownloadStatus.RATE_LIMITED, "Overpass is rate limiting us (429).")
    if code == 504:
        raise DownloadError(DownloadStatus.TIMEOUT, "Overpass timed out (504).")
    raise DownloadError(DownloadStatus.SOURCE_ERROR, f"Overpass answered {code}.")


def _raise_for_remark(body: dict[str, Any]) -> None:
    # Overpass reports runtime errors as a 200 with partial data and a remark.
    remark = body.get("remark")
    if remark is None:
        return
    status = DownloadStatus.TIMEOUT if "timed out" in str(remark) else DownloadStatus.SOURCE_ERROR
    raise DownloadError(status, f"Overpass stopped early: {remark}")


def _parse_elements(body: dict[str, Any]) -> list[OsmElement]:
    elements = body.get("elements")
    if not isinstance(elements, list):
        raise DownloadError(DownloadStatus.INVALID_RESPONSE, "Response has no element list.")
    try:
        return [_parse_element(e) for e in elements if e.get("type") in ("way", "relation")]
    except (AttributeError, KeyError, TypeError, ValueError) as e:
        raise DownloadError(
            DownloadStatus.INVALID_RESPONSE, f"Unexpected element shape: {e!r}"
        ) from e


def _parse_element(element: dict[str, Any]) -> OsmElement:
    tags = {str(k): str(v) for k, v in element.get("tags", {}).items()}
    if element["type"] == "way":
        return OsmWay(id=int(element["id"]), tags=tags, coords=_parse_coords(element["geometry"]))
    members = [
        OsmMember(role=str(m.get("role", "")), coords=_parse_coords(m["geometry"]))
        for m in element["members"]
        if m["type"] == "way" and m.get("geometry")
    ]
    return OsmRelation(id=int(element["id"]), tags=tags, members=members)


def _parse_coords(geometry: list[dict[str, Any]]) -> Coords:
    # Overpass puts null in place of points it could not resolve.
    return [(float(p["lon"]), float(p["lat"])) for p in geometry if p is not None]
