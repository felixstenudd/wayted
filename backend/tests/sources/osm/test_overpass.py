import json
from pathlib import Path

import httpx
import pytest

from app.sources.downloader import DownloadError, DownloadStatus
from app.sources.osm.overpass import OsmMember, OsmNode, OsmWay, build_query, run_query
from app.sources.tiles import Bounds

FIXTURES = Path(__file__).parents[2] / "fixtures"


def client_returning(response: httpx.Response) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(lambda request: response))


def test_build_query_orders_bbox_south_west_north_east() -> None:
    bounds = Bounds(west=18.0, south=59.0, east=18.5, north=59.5)
    query = build_query(['way["highway"]'], bounds, timeout_s=30)
    assert query == (
        '[out:json][timeout:30];(way["highway"](59.0,18.0,59.5,18.5););(._;>;);out body;'
    )


def test_build_query_joins_selectors_of_all_layers() -> None:
    bounds = Bounds(west=1.0, south=2.0, east=3.0, north=4.0)
    query = build_query(["way[a]", "relation[b]"], bounds, timeout_s=30)
    assert "(way[a](2.0,1.0,4.0,3.0);relation[b](2.0,1.0,4.0,3.0););" in query


def test_build_query_adds_areas_containing_the_centre() -> None:
    bounds = Bounds(west=1.0, south=2.0, east=3.0, north=4.0)
    query = build_query(["way[a]"], bounds, timeout_s=30, enclosing_selectors=["way[a]"])
    assert query == (
        "[out:json][timeout:30];is_in(3.0,2.0)->.enclosing;"
        "(way[a](2.0,1.0,4.0,3.0);way[a](pivot.enclosing););(._;>;);out body;"
    )


async def test_run_query_parses_nodes_ways_and_relations() -> None:
    body = json.loads((FIXTURES / "overpass_roads_parks.json").read_text())
    async with client_returning(httpx.Response(200, json=body)) as client:
        data = await run_query(client, "q")

    assert [n.id for n in data.nodes] == [1, 2, 3, 4, 5]
    assert data.nodes[1] == OsmNode(id=2, tags={"highway": "crossing"}, lon=18.061, lat=59.33)
    assert data.ways[0] == OsmWay(id=10, tags={"highway": "footway"}, node_ids=[1, 2, 5])
    assert data.ways[2].tags == {}
    (relation,) = data.relations
    assert relation.id == 30
    assert relation.members == [
        OsmMember(type="way", ref=20, role="outer"),
        OsmMember(type="way", ref=21, role="outer"),
        OsmMember(type="node", ref=5, role="label"),
    ]


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
    ("response", "status"),
    [
        (httpx.Response(429, text="nope"), DownloadStatus.RATE_LIMITED),
        (httpx.Response(504, text="nope"), DownloadStatus.TIMEOUT),
        (httpx.Response(500, text="nope"), DownloadStatus.SOURCE_ERROR),
        (httpx.Response(400, text="nope"), DownloadStatus.INVALID_RESPONSE),
        (httpx.Response(404, text="nope"), DownloadStatus.INVALID_RESPONSE),
        (httpx.Response(200, text=""), DownloadStatus.SOURCE_ERROR),
        (httpx.Response(200, text="<html>busy</html>"), DownloadStatus.SOURCE_ERROR),
    ],
)
async def test_run_query_maps_failed_responses(
    response: httpx.Response, status: DownloadStatus
) -> None:
    async with client_returning(response) as client:
        with pytest.raises(DownloadError) as caught:
            await run_query(client, "q")
    assert caught.value.status == status


async def test_rejected_query_reports_overpass_error_text() -> None:
    body = (FIXTURES / "overpass_400.html").read_text()
    async with client_returning(httpx.Response(400, text=body)) as client:
        with pytest.raises(DownloadError) as caught:
            await run_query(client, "q")

    message = caught.value.message
    assert caught.value.status == DownloadStatus.INVALID_RESPONSE
    assert message.startswith("Overpass rejected the query (400): Error: line 1: parse error:")
    assert "<" not in message
    assert "ODbL" not in message
    assert len(message) <= 250


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
    body = {"elements": [{"type": "node", "id": 1, "lat": 1.0, "lon": 2.0}], "remark": remark}
    async with client_returning(httpx.Response(200, json=body)) as client:
        with pytest.raises(DownloadError) as caught:
            await run_query(client, "q")
    assert caught.value.status == status


@pytest.mark.parametrize(
    "body",
    [
        [1, 2],
        {"no": "elements"},
        {"elements": ["not an object"]},
        {"elements": [{"type": "node", "id": 1}]},
        {"elements": [{"type": "way", "id": 1}]},
        {"elements": [{"type": "way", "id": 1, "nodes": ["x"]}]},
        {"elements": [{"type": "relation", "id": 1, "members": [{"type": "way"}]}]},
    ],
)
async def test_run_query_rejects_unexpected_shapes(body: object) -> None:
    async with client_returning(httpx.Response(200, json=body)) as client:
        with pytest.raises(DownloadError) as caught:
            await run_query(client, "q")
    assert caught.value.status == DownloadStatus.INVALID_RESPONSE
