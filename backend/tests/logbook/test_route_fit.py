import dataclasses
import itertools
from datetime import datetime
from typing import Any

import httpx
import pytest
from garmin_fit_sdk import Decoder, Profile, Stream

from app.logbook.routes.fit import REFERENCE_SPEED_M_S, Activity

from ..graph.raw_data import Conn
from .app_data import LonLat, add_other_users_route
from .test_route_export import MID, V0, V1, V2, add_heights, add_line, geodesic_m, save
from .test_route_instructions import Pool, build, road, roundabout, spur, steps, turn_off
from .test_route_instructions import save as save_steps

pytestmark = pytest.mark.db

_MESG_NAMES = {num: name.lower() for name, num in Profile["mesg_num"].items()}


@dataclasses.dataclass(frozen=True, slots=True)
class Fit:
    # message names in file order, a run of one kind as one
    order: list[str]
    messages: dict[str, list[dict[str, Any]]]

    def one(self, kind: str) -> dict[str, Any]:
        [mesg] = self.messages[f"{kind}_mesgs"]
        return mesg

    def all(self, kind: str) -> list[dict[str, Any]]:
        return self.messages.get(f"{kind}_mesgs", [])

    def points(self, kind: str) -> list[LonLat]:
        return [
            (round(degrees(m["position_long"]), 7), round(degrees(m["position_lat"]), 7))
            for m in self.all(kind)
        ]


def degrees(semicircles: int) -> float:
    return semicircles * 180 / 2**31


def decode(content: bytes) -> Fit:
    """Checks the file is whole and decodes without errors, then reads what the tests look at."""
    checker = Decoder(Stream.from_byte_array(bytearray(content)))
    assert checker.is_fit()
    # It reads the whole stream, so the messages are read from another.
    assert checker.check_integrity()
    kinds: list[str] = []
    messages, errors = Decoder(Stream.from_byte_array(bytearray(content))).read(
        mesg_listener=lambda num, _: kinds.append(_MESG_NAMES.get(num, str(num)))
    )
    assert errors == []
    return Fit([k for k, _ in itertools.groupby(kinds)], dict(messages))  # type: ignore[arg-type]


async def fit(client: httpx.AsyncClient, route_id: int) -> Fit:
    response = await client.get(f"/logbook/routes/{route_id}/fit")
    assert response.status_code == 200, response.text
    return decode(response.content)


def assert_timed_along_the_line(course: Fit, activity: Activity) -> None:
    records = course.all("record")
    times = [r["timestamp"] for r in records]
    distances = [r["distance"] for r in records]
    assert times == sorted(times)
    assert distances == sorted(distances)
    assert distances[0] == 0
    start: datetime = times[0]
    speed = REFERENCE_SPEED_M_S[activity]
    for record in records:
        assert (record["timestamp"] - start).total_seconds() == pytest.approx(
            record["distance"] / speed, abs=0.51
        )


async def test_a_route_downloads_as_a_fit_course_of_its_line(
    client: httpx.AsyncClient, app_conn: Conn
) -> None:
    points = [V0, MID, V1, V2]
    saved = await save(client, await add_line(app_conn, points), "Söder & Mälaren runt")

    response = await client.get(f"/logbook/routes/{saved['id']}/fit")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.ant.fit"
    assert (
        response.headers["content-disposition"] == 'attachment; filename="soder-malaren-runt.fit"'
    )
    course = decode(response.content)
    assert course.order == ["file_id", "course", "lap", "event", "record", "event"]
    assert course.one("file_id")["type"] == "course"
    assert course.one("course")["name"] == "Söder & Mälaren"
    assert course.one("course")["sport"] == "running"
    assert course.points("record") == points
    assert_timed_along_the_line(course, "running")
    records = course.all("record")
    assert records[-1]["distance"] == pytest.approx(saved["distance_m"], abs=0.01)
    assert records[-1]["distance"] == pytest.approx(await geodesic_m(app_conn, points), abs=0.01)
    assert all("altitude" not in r for r in records)
    assert course.all("course_point") == []
    lap = course.one("lap")
    assert lap["total_distance"] == records[-1]["distance"]
    assert (lap["start_time"], lap["timestamp"]) == (
        records[0]["timestamp"],
        records[-1]["timestamp"],
    )
    assert [(e["event"], e["event_type"], e["timestamp"]) for e in course.all("event")] == [
        ("timer", "start", records[0]["timestamp"]),
        ("timer", "stop_disable_all", records[-1]["timestamp"]),
    ]


async def test_a_cycling_course_is_for_cycling(client: httpx.AsyncClient, app_conn: Conn) -> None:
    saved = await save(client, await add_line(app_conn, [V0, V1, V2]), activity="cycling")

    course = await fit(client, saved["id"])

    assert course.one("course")["sport"] == "cycling"
    assert_timed_along_the_line(course, "cycling")


async def test_a_course_has_the_route_s_heights(client: httpx.AsyncClient, app_conn: Conn) -> None:
    # A metre per column, rising east, as in test_heights_are_sampled_for_every_point_when_saved.
    await add_heights(app_conn, "[rast.x]")
    saved = await save(client, await add_line(app_conn, [V0, MID, V1, V2]))

    course = await fit(client, saved["id"])

    # FIT keeps altitudes in fifths of a metre, so each is within a tenth.
    assert [r["altitude"] for r in course.all("record")] == pytest.approx(
        [50.5, 53.0, 55.5, 60.5], abs=0.11
    )


@pytest.mark.parametrize(
    "points",
    [
        [V0, V1, (20.0005, 63.801), V0],
        [V1, (20.002, 63.801), (20.002, 63.8), V1, (20.0, 63.8), (20.0, 63.801), V1],
    ],
    ids=["loop", "self-crossing loop"],
)
async def test_loops_export_every_point_in_route_order(
    client: httpx.AsyncClient, app_conn: Conn, points: list[LonLat]
) -> None:
    saved = await save(client, await add_line(app_conn, points), shape="loop")

    course = await fit(client, saved["id"])

    assert course.points("record") == points
    assert_timed_along_the_line(course, "running")
    assert course.all("record")[-1]["distance"] == pytest.approx(saved["distance_m"], abs=0.01)


async def test_other_users_routes_do_not_download(
    client: httpx.AsyncClient, app_conn: Conn
) -> None:
    route_id = await add_other_users_route(app_conn)

    for path in (f"/logbook/routes/{route_id}/fit", f"/logbook/routes/{route_id + 1}/fit"):
        assert (await client.get(path)).status_code == 404


async def stored_turns(conn: Conn, route_id: int) -> list[tuple[int, str]]:
    cur = await conn.execute(
        "SELECT point, maneuver FROM app.route_instructions WHERE route_id = %s ORDER BY seq",
        (route_id,),
    )
    return await cur.fetchall()


def assert_course_points_at_their_records(course: Fit, turns: list[tuple[int, str]]) -> None:
    """Each course point sits on the record at its instruction's point, with its time and
    distance, so a watch counts down to it along the line."""
    records = course.all("record")
    course_points = course.all("course_point")
    assert len(course_points) == len(turns)
    keys = ("timestamp", "distance", "position_lat", "position_long")
    for course_point, (point, _) in zip(course_points, turns, strict=True):
        assert {k: course_point[k] for k in keys} == {k: records[point][k] for k in keys}
        assert len(course_point.get("name") or "") <= 15


async def test_every_instruction_is_a_course_point(
    client: httpx.AsyncClient, app_conn: Conn, mapper_pool: Pool
) -> None:
    saved = await save_steps(client, await steps(app_conn, await spur(app_conn, mapper_pool)))

    course = await fit(client, saved["id"])

    assert course.order == [
        "file_id",
        "course",
        "lap",
        "event",
        "record",
        "course_point",
        "event",
    ]
    assert [(p["type"], p["name"]) for p in course.all("course_point")] == [
        ("left", "Gränd"),
        ("u_turn", "Gränd"),
        ("left", "Storgatan"),
    ]
    assert_course_points_at_their_records(course, await stored_turns(app_conn, saved["id"]))


@pytest.mark.parametrize(
    ("nodes", "point"),
    [
        ([20, 13, 12, 11, 22], ("straight", "Exit 2 Norrväge")),
        ([20, 13, 12, 11, 14, 23], ("left", "Exit 3 E4")),
    ],
    ids=["straight on", "left"],
)
async def test_a_roundabout_points_the_way_its_exit_goes(
    client: httpx.AsyncClient,
    app_conn: Conn,
    mapper_pool: Pool,
    nodes: list[int],
    point: tuple[str, str],
) -> None:
    await roundabout(app_conn, mapper_pool)
    saved = await save_steps(client, await steps(app_conn, nodes))

    course = await fit(client, saved["id"])

    assert [(p["type"], p["name"]) for p in course.all("course_point")] == [point]
    assert_course_points_at_their_records(course, await stored_turns(app_conn, saved["id"]))


@pytest.mark.parametrize(
    ("tags", "name"),
    [
        (road("Kungsträdgårdsgatan"), "Kungsträdgårdsg"),
        (road(None, "living_street"), "living street"),
    ],
)
async def test_course_point_names_are_road_labels_a_watch_can_show(
    client: httpx.AsyncClient, app_conn: Conn, mapper_pool: Pool, tags: dict[str, str], name: str
) -> None:
    await turn_off(app_conn, mapper_pool, (2, 2), tags)
    saved = await save_steps(client, await steps(app_conn, [1, 2, 4]))

    course = await fit(client, saved["id"])

    assert [(p["type"], p["name"]) for p in course.all("course_point")] == [("left", name)]


async def test_a_self_crossing_loop_has_its_course_points_in_route_order(
    client: httpx.AsyncClient, app_conn: Conn, mapper_pool: Pool
) -> None:
    # The figure of eight of test_a_self_crossing_loop_has_its_turns_in_route_order.
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
    saved = await save_steps(client, await steps(app_conn, [p[0] for p in corners]), shape="loop")

    course = await fit(client, saved["id"])

    assert len(course.all("record")) == len(corners)
    assert [(p["type"], p["name"]) for p in course.all("course_point")] == [
        ("left", "Två"),
        ("left", "Tre"),
        ("left", "Fyra"),
        ("right", "Sex"),
        ("right", "Sju"),
        ("right", "Åtta"),
    ]
    distances = [p["distance"] for p in course.all("course_point")]
    assert distances == sorted(set(distances))
    assert_course_points_at_their_records(course, await stored_turns(app_conn, saved["id"]))
