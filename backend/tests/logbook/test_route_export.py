import dataclasses
import itertools
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import httpx
import pytest
import xmlschema
from psycopg import AsyncConnection
from psycopg.rows import TupleRow

from app.sources.tiles import Tile

from .app_data import LonLat, add_edge, add_other_users_route

pytestmark = pytest.mark.db

type Conn = AsyncConnection[TupleRow]

GPX_SCHEMA = xmlschema.XMLSchema(Path(__file__).parents[1] / "fixtures" / "gpx-1.1.xsd")
NS = {"gpx": "http://www.topografix.com/GPX/1/1"}

V0 = (20.0, 63.8)
MID = (20.0005, 63.8005)
V1 = (20.001, 63.8)
V2 = (20.002, 63.8)


@dataclasses.dataclass(frozen=True, slots=True)
class Gpx:
    names: list[str]
    points: list[LonLat]
    heights: list[float]


def parse(text: str) -> Gpx:
    """Validates the GPX against the official 1.1 schema, then reads what the tests look at."""
    GPX_SCHEMA.validate(text)
    root = ET.fromstring(text.encode())
    names = [e.text or "" for e in root.findall("./gpx:metadata/gpx:name", NS)] + [
        e.text or "" for e in root.findall("./gpx:trk/gpx:name", NS)
    ]
    trkpts = root.findall("./gpx:trk/gpx:trkseg/gpx:trkpt", NS)
    return Gpx(
        names=names,
        points=[(float(p.attrib["lon"]), float(p.attrib["lat"])) for p in trkpts],
        heights=[float(e.text or "") for e in root.findall(".//gpx:trkpt/gpx:ele", NS)],
    )


async def add_heights(conn: Conn, heights: str, *, columns: int = 100) -> None:
    """A height model of cells 0.0002 by 0.0001 degrees, `columns` east from 19.99 and 200 rows
    south from 63.81, each cell as high as the map algebra expression."""
    await conn.execute(
        """
        INSERT INTO raw.elevation_tiles (z, x, y, rast)
        SELECT %(z)s, %(x)s, %(y)s, ST_MapAlgebra(
            ST_AddBand(
                ST_MakeEmptyRaster(%(columns)s, 200, 19.99, 63.81, 0.0002, -0.0001, 0, 0, 4326),
                '32BF'::text, 0, -32767
            ),
            1, '32BF', %(heights)s
        )
        """,
        {
            **dataclasses.asdict(Tile.from_lat_lon(63.8, 20.0, 14)),
            "columns": columns,
            "heights": heights,
        },
    )


async def add_line(conn: Conn, points: list[LonLat]) -> list[int]:
    """Edges joining `points` in order, each as long as it really is; a repeated point is the
    same vertex."""
    vertex = {p: n for n, p in enumerate(dict.fromkeys(points))}
    edges = [
        await add_edge(conn, vertex[a], vertex[b], [a, b]) for a, b in itertools.pairwise(points)
    ]
    await conn.execute("UPDATE graph.edges SET length_m = ST_Length(geom::geography)")
    return edges


async def save(
    client: httpx.AsyncClient, edges: list[int], name: str = "Morning loop", **overrides: Any
) -> dict[str, Any]:
    body = {
        "name": name,
        "activity": "running",
        "shape": "point_to_point",
        "target_distance_m": 5000,
        "edges": [{"edge_id": e, "forward": True} for e in edges],
    } | overrides
    response = await client.post("/logbook/routes", json=body)
    assert response.status_code == 201, response.text
    saved: dict[str, Any] = response.json()
    return saved


async def gpx(client: httpx.AsyncClient, route_id: int) -> Gpx:
    response = await client.get(f"/logbook/routes/{route_id}/gpx")
    assert response.status_code == 200, response.text
    return parse(response.text)


async def geodesic_m(conn: Conn, points: list[LonLat]) -> float:
    line = "LINESTRING(" + ", ".join(f"{lon} {lat}" for lon, lat in points) + ")"
    cur = await conn.execute("SELECT ST_Length(ST_GeomFromText(%s, 4326)::geography)", (line,))
    row = await cur.fetchone()
    assert row is not None
    length: float = row[0]
    return length


async def elevations(conn: Conn, route_id: int) -> list[float] | None:
    cur = await conn.execute("SELECT elevations FROM app.routes WHERE id = %s", (route_id,))
    row = await cur.fetchone()
    assert row is not None
    heights: list[float] | None = row[0]
    return heights


async def test_a_route_downloads_as_a_gpx_track_of_its_line(
    client: httpx.AsyncClient, app_conn: Conn
) -> None:
    saved = await save(client, await add_line(app_conn, [V0, MID, V1, V2]), "Söder & <Mälaren>")

    response = await client.get(f"/logbook/routes/{saved['id']}/gpx")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/gpx+xml"
    assert response.headers["content-disposition"] == 'attachment; filename="soder-malaren.gpx"'
    track = parse(response.text)
    assert track.names == ["Söder & <Mälaren>"] * 2
    assert track.points == [V0, MID, V1, V2]
    assert track.heights == []
    assert await geodesic_m(app_conn, track.points) == pytest.approx(saved["distance_m"])


async def test_heights_are_sampled_for_every_point_when_saved(
    client: httpx.AsyncClient, app_conn: Conn
) -> None:
    # A metre per column, rising east: blended between cells, a height is the column under it.
    await add_heights(app_conn, "[rast.x]")
    saved = await save(client, await add_line(app_conn, [V0, MID, V1, V2]))

    expected = [50.5, 53.0, 55.5, 60.5]
    assert await elevations(app_conn, saved["id"]) == pytest.approx(expected)
    assert (await gpx(client, saved["id"])).heights == pytest.approx(expected)


@pytest.mark.parametrize(
    ("columns", "heights"),
    [(57, "[rast.x]"), (100, "CASE WHEN [rast.x] > 57 THEN -32767 ELSE [rast.x] END")],
    ids=["off the height model", "no data"],
)
async def test_a_route_partly_without_heights_has_none(
    client: httpx.AsyncClient, app_conn: Conn, columns: int, heights: str
) -> None:
    # Both leave V2 without a height.
    await add_heights(app_conn, heights, columns=columns)
    saved = await save(client, await add_line(app_conn, [V0, MID, V1, V2]))

    assert await elevations(app_conn, saved["id"]) is None
    track = await gpx(client, saved["id"])
    assert track.heights == []
    assert len(track.points) == 4


@pytest.mark.parametrize(
    "points",
    [
        [V0, V1, (20.0005, 63.801), V0],
        # A figure of eight, through V1 at the start, the middle and the end.
        [V1, (20.002, 63.801), (20.002, 63.8), V1, (20.0, 63.8), (20.0, 63.801), V1],
    ],
    ids=["loop", "self-crossing loop"],
)
async def test_loops_export_every_point_in_route_order(
    client: httpx.AsyncClient, app_conn: Conn, points: list[LonLat]
) -> None:
    saved = await save(client, await add_line(app_conn, points), shape="loop")

    track = await gpx(client, saved["id"])

    assert track.points == points
    assert await geodesic_m(app_conn, track.points) == pytest.approx(saved["distance_m"])


async def test_other_users_routes_do_not_download(
    client: httpx.AsyncClient, app_conn: Conn
) -> None:
    route_id = await add_other_users_route(app_conn)

    for path in (f"/logbook/routes/{route_id}/gpx", f"/logbook/routes/{route_id + 1}/gpx"):
        assert (await client.get(path)).status_code == 404
