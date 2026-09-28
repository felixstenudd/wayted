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


@dataclass(frozen=True, slots=True)
class OsmNode:
    id: int
    tags: dict[str, str]
    lon: float
    lat: float


@dataclass(frozen=True, slots=True)
class OsmWay:
    id: int
    tags: dict[str, str]
    node_ids: list[int]


@dataclass(frozen=True, slots=True)
class OsmMember:
    type: str  # "node", "way" or "relation"
    ref: int
    role: str


@dataclass(frozen=True, slots=True)
class OsmRelation:
    id: int
    tags: dict[str, str]
    members: list[OsmMember]


@dataclass(frozen=True, slots=True)
class OsmData:
    nodes: list[OsmNode]
    ways: list[OsmWay]
    relations: list[OsmRelation]


def build_query(
    selectors: Sequence[str],
    bounds: Bounds,
    timeout_s: int = QUERY_TIMEOUT_S,
    enclosing_selectors: Sequence[str] = (),
) -> str:
    """
    Return a query for everything matching the selectors inside bounds, plus every node and
    member way they use, so the result is complete OSM data with ids.

    enclosing_selectors are also matched against areas containing the centre of bounds. A bbox
    only finds areas whose outline lies in or crosses it, so an area covering all of bounds,
    such as a large park, is otherwise missed.
    """
    # Overpass orders bbox: south, west, north, east.
    bbox = f"({bounds.south},{bounds.west},{bounds.north},{bounds.east})"
    union = "".join(f"{selector}{bbox};" for selector in selectors)
    if not enclosing_selectors:
        return f"[out:json][timeout:{timeout_s}];({union});(._;>;);out body;"
    centre = f"{(bounds.south + bounds.north) / 2},{(bounds.west + bounds.east) / 2}"
    union += "".join(f"{selector}(pivot.enclosing);" for selector in enclosing_selectors)
    return (
        f"[out:json][timeout:{timeout_s}];is_in({centre})->.enclosing;({union});(._;>;);out body;"
    )


def new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=HTTP_TIMEOUT_S,
    )


async def run_query(client: httpx.AsyncClient, query: str) -> OsmData:
    """Send a query and return its elements. Raises DownloadError on any failure."""
    response = await client.post(OVERPASS_URL, data={"data": query})
    _raise_for_status(response)
    try:
        body = response.json()
    except ValueError as e:
        raise DownloadError(DownloadStatus.SOURCE_ERROR, "Overpass answered with non-JSON.") from e
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


def _parse_elements(body: dict[str, Any]) -> OsmData:
    elements = body.get("elements")
    if not isinstance(elements, list):
        raise DownloadError(DownloadStatus.INVALID_RESPONSE, "Response has no element list.")
    data = OsmData(nodes=[], ways=[], relations=[])
    try:
        for e in elements:
            tags = {str(k): str(v) for k, v in e.get("tags", {}).items()}
            if e["type"] == "node":
                data.nodes.append(
                    OsmNode(id=int(e["id"]), tags=tags, lon=float(e["lon"]), lat=float(e["lat"]))
                )
            elif e["type"] == "way":
                node_ids = [int(n) for n in e["nodes"]]
                data.ways.append(OsmWay(id=int(e["id"]), tags=tags, node_ids=node_ids))
            elif e["type"] == "relation":
                members = [
                    OsmMember(type=str(m["type"]), ref=int(m["ref"]), role=str(m.get("role", "")))
                    for m in e["members"]
                ]
                data.relations.append(OsmRelation(id=int(e["id"]), tags=tags, members=members))
    except (AttributeError, KeyError, TypeError, ValueError) as e:
        raise DownloadError(
            DownloadStatus.INVALID_RESPONSE, f"Unexpected element shape: {e!r}"
        ) from e
    return data
