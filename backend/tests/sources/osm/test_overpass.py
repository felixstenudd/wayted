import json
from pathlib import Path

import httpx
import pytest

from app.sources.downloader import DownloadError, DownloadStatus
from app.sources.osm.overpass import OsmRelation, OsmWay, build_query, run_query
from app.sources.tiles import Bounds

FIXTURES = Path(__file__).parents[2] / "fixtures"


def client_returning(response: httpx.Response) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(lambda request: response))


def test_build_query_orders_bbox_south_west_north_east() -> None:
    bounds = Bounds(west=18.0, south=59.0, east=18.5, north=59.5)
    query = build_query(['way["highway"]'], bounds, timeout_s=30)
    assert query == '[out:json][timeout:30];(way["highway"](59.0,18.0,59.5,18.5););out tags geom;'


def test_build_query_joins_selectors() -> None:
    bounds = Bounds(west=1.0, south=2.0, east=3.0, north=4.0)
    query = build_query(["way[a]", "relation[b]"], bounds, timeout_s=30)
    assert "(way[a](2.0,1.0,4.0,3.0);relation[b](2.0,1.0,4.0,3.0););" in query


async def test_run_query_parses_ways_and_relations() -> None:
    body = json.loads((FIXTURES / "overpass_parks.json").read_text())
    async with client_returning(httpx.Response(200, json=body)) as client:
        elements = await run_query(client, "q")
    way, relation = elements
    assert isinstance(way, OsmWay)
    assert way.id == 1001
    assert way.tags["name"] == "Small park"
    assert way.coords[0] == (18.060, 59.330)
    assert isinstance(relation, OsmRelation)
    assert [m.role for m in relation.members] == ["outer", "outer", "inner"]


async def test_run_query_sends_query_as_form_data() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"elements": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await run_query(client, "[out:json];")
    assert seen[0].method == "POST"
    assert seen[0].content == b"data=%5Bout%3Ajson%5D%3B"


@pytest.mark.parametrize(
    ("code", "status"),
    [
        (429, DownloadStatus.RATE_LIMITED),
        (504, DownloadStatus.TIMEOUT),
        (500, DownloadStatus.SOURCE_ERROR),
        (400, DownloadStatus.SOURCE_ERROR),
    ],
)
async def test_run_query_maps_http_errors(code: int, status: DownloadStatus) -> None:
    async with client_returning(httpx.Response(code, text="nope")) as client:
        with pytest.raises(DownloadError) as caught:
            await run_query(client, "q")
    assert caught.value.status == status


@pytest.mark.parametrize(
    ("remark", "status"),
    [
        (
            'runtime error: Query timed out in "query" at line 1 after 91 seconds.',
            DownloadStatus.TIMEOUT,
        ),
        (
            "runtime error: Query run out of memory using about 2048 MB of RAM.",
            DownloadStatus.SOURCE_ERROR,
        ),
    ],
)
async def test_run_query_rejects_partial_data_with_remark(
    remark: str, status: DownloadStatus
) -> None:
    body = {"elements": [{"type": "way", "id": 1, "geometry": []}], "remark": remark}
    async with client_returning(httpx.Response(200, json=body)) as client:
        with pytest.raises(DownloadError) as caught:
            await run_query(client, "q")
    assert caught.value.status == status


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="<html>not json</html>"),
        httpx.Response(200, json=[1, 2]),
        httpx.Response(200, json={"no": "elements"}),
        httpx.Response(200, json={"elements": [{"type": "way", "id": 1}]}),
        httpx.Response(200, json={"elements": [{"type": "way", "id": 1, "geometry": [{"x": 1}]}]}),
        httpx.Response(200, json={"elements": ["not an object"]}),
    ],
)
async def test_run_query_rejects_malformed_bodies(response: httpx.Response) -> None:
    async with client_returning(response) as client:
        with pytest.raises(DownloadError) as caught:
            await run_query(client, "q")
    assert caught.value.status == DownloadStatus.INVALID_RESPONSE


async def test_run_query_skips_nodes_and_null_points() -> None:
    body = {
        "elements": [
            {"type": "node", "id": 9, "lat": 1.0, "lon": 2.0},
            {"type": "way", "id": 1, "geometry": [{"lat": 1.0, "lon": 2.0}, None]},
        ]
    }
    async with client_returning(httpx.Response(200, json=body)) as client:
        elements = await run_query(client, "q")
    assert elements == [OsmWay(id=1, tags={}, coords=[(2.0, 1.0)])]
