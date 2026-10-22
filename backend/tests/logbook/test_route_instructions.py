import dataclasses
import itertools
import xml.etree.ElementTree as ET
from typing import Any

import httpx
import pytest
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from app.graph import map_pending
from app.sources.tiles import Tile

from ..graph.raw_data import ORIGIN_LAT, ORIGIN_LON, STEP, Conn, Point, add_line
from .test_route_export import GPX_SCHEMA, NS

pytestmark = pytest.mark.db

type Pool = AsyncConnectionPool[Conn]
type Step = dict[str, Any]
# (seq, point, distance_m rounded, maneuver, exit, angle, name, way_class)
type Row = tuple[int, int, int, str, int | None, int, str | None, str | None]


def road(name: str | None, highway: str = "residential", **tags: str) -> dict[str, str]:
    return {"highway": highway} | ({"name": name} if name else {}) | tags


async def steps(conn: Conn, nodes: list[int]) -> list[Step]:
    """The edges from node to node in order, each the way it is travelled."""
    found = []
    for a, b in itertools.pairwise(nodes):
        cur = await conn.execute(
            """
            SELECT id, source = %(a)s FROM graph.edges
            WHERE (source, target) IN ((%(a)s, %(b)s), (%(b)s, %(a)s))
            """,
            {"a": a, "b": b},
        )
        rows = await cur.fetchall()
        assert len(rows) == 1, (a, b, rows)
        found.append({"edge_id": rows[0][0], "forward": rows[0][1]})
    return found


async def save(client: httpx.AsyncClient, route: list[Step], **overrides: Any) -> dict[str, Any]:
    body = {
        "name": "Turns",
        "activity": "running",
        "shape": "point_to_point",
        "target_distance_m": 5000,
        "edges": route,
    } | overrides
    response = await client.post("/logbook/routes", json=body)
    assert response.status_code == 201, response.text
    saved: dict[str, Any] = response.json()
    return saved


async def stored(conn: Conn, route_id: int) -> list[Row]:
    cur = await conn.execute(
        """
        SELECT seq, point, round(distance_m)::int, maneuver, exit, angle, name, way_class
        FROM app.route_instructions WHERE route_id = %s ORDER BY seq
        """,
        (route_id,),
    )
    return await cur.fetchall()


async def edge_ends_m(conn: Conn, route: list[Step]) -> list[int]:
    """How far along the route each step ends, rounded."""
    cur = await conn.execute(
        """
        SELECT round(sum(e.length_m) OVER (ORDER BY s.n))::int
        FROM unnest(%s::bigint[]) WITH ORDINALITY AS s (id, n)
        JOIN graph.edges e ON e.id = s.id
        ORDER BY s.n
        """,
        ([s["edge_id"] for s in route],),
    )
    return [m for (m,) in await cur.fetchall()]


async def build(
    conn: Conn, mapper_pool: Pool, ways: list[tuple[list[Point], dict[str, str]]]
) -> None:
    """The ways as OSM data, numbered from 1, mapped into the graph."""
    for way_id, (points, tags) in enumerate(ways, start=1):
        await add_line(conn, way_id, points, tags)
    await map_pending(mapper_pool.connection)


# Storgatan runs east through node 2, where a road leaves for node 4.
async def turn_off(
    conn: Conn, mapper_pool: Pool, to: tuple[int, int], tags: dict[str, str]
) -> None:
    await build(
        conn,
        mapper_pool,
        [
            ([(1, 0, 0), (2, 2, 0), (3, 4, 0)], road("Storgatan")),
            ([(2, 2, 0), (4, *to)], tags),
        ],
    )


# Storgatan east to node 2, then the dead end Gränd north to node 4 and back, then on east.
async def spur(conn: Conn, mapper_pool: Pool) -> list[int]:
    await build(
        conn,
        mapper_pool,
        [
            ([(1, 0, 0), (2, 2, 0), (3, 4, 0)], road("Storgatan")),
            ([(2, 2, 0), (4, 2, 2)], road("Gränd", "service")),
        ],
    )
    return [1, 2, 4, 2, 3]


# A roundabout, anticlockwise from south (13) to east (12), north (11) and west (14), with a road
# out at each: the east one a footway, which cycling may not use.
async def roundabout(conn: Conn, mapper_pool: Pool) -> None:
    await build(
        conn,
        mapper_pool,
        [
            (
                [(13, 5, 4), (12, 6, 5), (11, 5, 6), (14, 4, 5), (13, 5, 4)],
                road(None, junction="roundabout"),
            ),
            ([(20, 5, 1), (13, 5, 4)], road("Sydvägen")),
            ([(12, 6, 5), (21, 8, 5)], road("Östvägen", "footway")),
            ([(11, 5, 6), (22, 5, 9)], road("Norrvägen")),
            ([(14, 4, 5), (23, 2, 5)], road(None, ref="E4")),
        ],
    )


@pytest.mark.parametrize(
    ("to", "maneuver"),
    [
        ((4, 1), "slight_left"),
        ((2, 2), "left"),
        ((0, 1), "sharp_left"),
        ((4, -1), "slight_right"),
        ((2, -2), "right"),
        ((0, -1), "sharp_right"),
    ],
)
async def test_turning_off_onto_another_road_is_an_instruction(
    client: httpx.AsyncClient,
    app_conn: Conn,
    mapper_pool: Pool,
    to: tuple[int, int],
    maneuver: str,
) -> None:
    await turn_off(app_conn, mapper_pool, to, road("Kungsgatan"))
    route = await steps(app_conn, [1, 2, 4])

    saved = await save(client, route)

    [row] = await stored(app_conn, saved["id"])
    seq, point, distance_m, stored_maneuver, exit_, angle, name, way_class = row
    assert (seq, point, stored_maneuver, exit_, name, way_class) == (
        0,
        1,
        maneuver,
        None,
        "Kungsgatan",
        "residential",
    )
    assert distance_m == (await edge_ends_m(app_conn, route))[0]
    assert (angle < 0) == maneuver.endswith("left")
    assert saved["instructions"] == [
        {
            "seq": 0,
            "distance_m": pytest.approx(saved["edges"][0]["length_m"]),
            "maneuver": maneuver,
            "exit": None,
            "name": "Kungsgatan",
            "way_class": "residential",
        }
    ]


@pytest.mark.parametrize(
    ("side", "expected"),
    [((2, -2), []), ((4, 0), [("left", "Storgatan")])],
    ids=["side road off the bend", "side road straight on"],
)
async def test_a_road_bending_through_a_junction_is_followed_without_one(
    client: httpx.AsyncClient,
    app_conn: Conn,
    mapper_pool: Pool,
    side: tuple[int, int],
    expected: list[tuple[str, str]],
) -> None:
    # Storgatan bends left by about 63 degrees at node 2. Only when another road there goes on
    # closer to straight does staying on it need saying.
    await build(
        app_conn,
        mapper_pool,
        [
            ([(1, 0, 0), (2, 2, 0), (3, 4, 2)], road("Storgatan")),
            ([(2, 2, 0), (4, *side)], road("Lillgatan")),
        ],
    )

    saved = await save(client, await steps(app_conn, [1, 2, 3]))

    assert [(r[3], r[6]) for r in await stored(app_conn, saved["id"])] == expected


async def test_going_straight_on_where_the_name_changes_needs_none(
    client: httpx.AsyncClient, app_conn: Conn, mapper_pool: Pool
) -> None:
    await build(
        app_conn,
        mapper_pool,
        [
            ([(1, 0, 0), (2, 2, 0)], road("Storgatan")),
            ([(2, 2, 0), (3, 4, 0)], road("Drottninggatan")),
            ([(2, 2, 0), (4, 2, 2)], road("Lillgatan")),
        ],
    )

    saved = await save(client, await steps(app_conn, [1, 2, 3]))

    assert await stored(app_conn, saved["id"]) == []


async def test_a_bend_where_one_way_meets_the_next_needs_none(
    client: httpx.AsyncClient, app_conn: Conn, mapper_pool: Pool
) -> None:
    # A right angle, but nowhere else to go.
    await build(
        app_conn,
        mapper_pool,
        [
            ([(1, 0, 0), (2, 2, 0)], road("Storgatan")),
            ([(2, 2, 0), (3, 2, 2)], road("Kungsgatan")),
        ],
    )

    saved = await save(client, await steps(app_conn, [1, 2, 3]))

    assert await stored(app_conn, saved["id"]) == []


async def test_the_end_of_a_dead_end_is_a_u_turn(
    client: httpx.AsyncClient, app_conn: Conn, mapper_pool: Pool
) -> None:
    route = await steps(app_conn, await spur(app_conn, mapper_pool))

    saved = await save(client, route)

    ends = await edge_ends_m(app_conn, route)
    assert await stored(app_conn, saved["id"]) == [
        (0, 1, ends[0], "left", None, -90, "Gränd", "service"),
        (1, 2, ends[1], "u_turn", None, 180, "Gränd", "service"),
        (2, 3, ends[2], "left", None, -90, "Storgatan", "residential"),
    ]


@pytest.mark.parametrize(
    ("activity", "nodes", "exit_", "angle", "name"),
    [
        ("running", [20, 13, 12, 11, 22], 2, 0, "Norrvägen"),
        # The footway out east is no exit for a bike.
        ("cycling", [20, 13, 12, 11, 22], 1, 0, "Norrvägen"),
        # No name: the ref says which road it is.
        ("running", [20, 13, 12, 11, 14, 23], 3, -90, "E4"),
    ],
)
async def test_a_roundabout_is_one_instruction_counting_its_exits(
    client: httpx.AsyncClient,
    app_conn: Conn,
    mapper_pool: Pool,
    activity: str,
    nodes: list[int],
    exit_: int,
    angle: int,
    name: str,
) -> None:
    await roundabout(app_conn, mapper_pool)
    route = await steps(app_conn, nodes)

    saved = await save(client, route, activity=activity)

    [row] = await stored(app_conn, saved["id"])
    assert row[:5] == (0, 1, (await edge_ends_m(app_conn, route))[0], "roundabout", exit_)
    assert row[5] == pytest.approx(angle, abs=3)
    assert row[6:] == (name, "residential")


async def test_a_self_crossing_loop_has_its_turns_in_route_order(
    client: httpx.AsyncClient, app_conn: Conn, mapper_pool: Pool
) -> None:
    # A figure of eight through node 1: a square anticlockwise to the north-east, straight across
    # node 1 and a square clockwise to the south-west. Each corner has a path off it, so it is a
    # junction.
    c, a, b, d = (1, 2, 2), (2, 4, 2), (3, 4, 4), (4, 2, 4)
    f, g, h = (5, 2, 0), (6, 0, 0), (7, 0, 2)
    sides = ["Ett", "Två", "Tre", "Fyra", "Fem", "Sex", "Sju", "Åtta"]
    corners = [c, a, b, d, c, f, g, h, c]
    stubs = [(a, (6, 2)), (b, (4, 6)), (d, (2, 6)), (f, (2, -2)), (g, (-2, 0)), (h, (-2, 2))]
    await build(
        app_conn,
        mapper_pool,
        [([p, q], road(n)) for (p, q), n in zip(itertools.pairwise(corners), sides, strict=True)]
        + [([p, (100 + n, *xy)], road(None, "path")) for n, (p, xy) in enumerate(stubs)],
    )
    route = await steps(app_conn, [p[0] for p in corners])

    saved = await save(client, route, shape="loop")

    rows = await stored(app_conn, saved["id"])
    assert [(r[1], r[3], r[6]) for r in rows] == [
        (1, "left", "Två"),
        (2, "left", "Tre"),
        (3, "left", "Fyra"),
        (5, "right", "Sex"),
        (6, "right", "Sju"),
        (7, "right", "Åtta"),
    ]
    distances = [r[2] for r in rows]
    assert distances == sorted(set(distances))


@pytest.mark.parametrize(
    ("settings", "maneuvers"),
    [
        ({}, ["left"]),
        ({"turn": 95}, ["slight_left"]),
        ({"sharp": 85}, ["sharp_left"]),
        ({"u_turn": 85}, ["u_turn"]),
        ({"slight": 95, "turn": 100}, []),
    ],
)
async def test_the_turn_s_size_picks_its_band(
    app_conn: Conn,
    mapper_pool: Pool,
    api_pool: Pool,
    settings: dict[str, float],
    maneuvers: list[str],
) -> None:
    # A right angle to the left.
    await turn_off(app_conn, mapper_pool, (2, 2), road("Kungsgatan"))
    route = await steps(app_conn, [1, 2, 4])

    async with api_pool.connection() as conn:
        cur = await conn.execute(
            "SELECT maneuver FROM routing.instructions(%s, %s, 'running', %s)",
            (
                [s["edge_id"] for s in route],
                [s["forward"] for s in route],
                Jsonb({"instructions": settings}),
            ),
        )
        assert [m for (m,) in await cur.fetchall()] == maneuvers


@dataclasses.dataclass(frozen=True, slots=True)
class Waypoint:
    lon: float
    lat: float
    ele: float | None
    name: str
    type: str


def waypoints(text: str) -> list[Waypoint]:
    GPX_SCHEMA.validate(text)
    root = ET.fromstring(text.encode())
    found = []
    for w in root.findall("./gpx:wpt", NS):
        ele = w.find("gpx:ele", NS)
        found.append(
            Waypoint(
                lon=float(w.attrib["lon"]),
                lat=float(w.attrib["lat"]),
                ele=float(ele.text or "") if ele is not None else None,
                name=w.findtext("gpx:name", "", NS),
                type=w.findtext("gpx:type", "", NS),
            )
        )
    return found


def grid(x: int, y: int) -> tuple[float, float]:
    return (round(ORIGIN_LON + x * STEP, 7), round(ORIGIN_LAT + y * STEP, 7))


async def test_a_gpx_has_a_waypoint_per_instruction_before_its_track(
    client: httpx.AsyncClient, app_conn: Conn, mapper_pool: Pool
) -> None:
    # 42 m everywhere around the grid's origin.
    await app_conn.execute(
        """
        INSERT INTO raw.elevation_tiles (z, x, y, rast)
        SELECT %(z)s, %(x)s, %(y)s, ST_MapAlgebra(
            ST_AddBand(
                ST_MakeEmptyRaster(100, 200, 17.99, 59.31, 0.0002, -0.0001, 0, 0, 4326),
                '32BF'::text, 0, -32767
            ),
            1, '32BF', '42'
        )
        """,
        dataclasses.asdict(Tile.from_lat_lon(ORIGIN_LAT, ORIGIN_LON, 14)),
    )
    saved = await save(client, await steps(app_conn, await spur(app_conn, mapper_pool)))

    response = await client.get(f"/logbook/routes/{saved['id']}/gpx")

    assert response.status_code == 200
    assert waypoints(response.text) == [
        Waypoint(*grid(2, 0), 42, "Left onto Gränd", "left"),
        Waypoint(*grid(2, 2), 42, "Turn around", "u_turn"),
        Waypoint(*grid(2, 0), 42, "Left onto Storgatan", "left"),
    ]


@pytest.mark.parametrize(
    ("scenario", "name"),
    [("path", "Slight right onto path"), ("roundabout", "Roundabout, exit 2 onto Norrvägen")],
)
async def test_gpx_waypoints_say_what_to_do(
    client: httpx.AsyncClient, app_conn: Conn, mapper_pool: Pool, scenario: str, name: str
) -> None:
    if scenario == "path":
        # A path without a name is called a path.
        await turn_off(app_conn, mapper_pool, (4, -1), road(None, "path"))
        nodes = [1, 2, 4]
    else:
        await roundabout(app_conn, mapper_pool)
        nodes = [20, 13, 12, 11, 22]
    saved = await save(client, await steps(app_conn, nodes))

    response = await client.get(f"/logbook/routes/{saved['id']}/gpx")

    [waypoint] = waypoints(response.text)
    assert waypoint.name == name
    assert waypoint.ele is None
