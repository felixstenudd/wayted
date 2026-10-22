"""Saved routes as FIT course files, which Garmin watches and bike computers follow turn by turn.

Encoded with Garmin's FIT SDK. Its encoder matches a message to an earlier definition without
regard to field order, a known source of corrupt files, so each message type is written by one
helper below that always passes the same fields in the same order.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

from garmin_fit_sdk import Encoder, Profile

type Activity = Literal["running", "cycling"]

# A watch shows a course's and a course point's name in about this many characters.
NAME_MAX_CHARS = 15
# Without a word boundary at least this far in, the name is cut mid-word instead: "A" alone says
# less than "A Kungsträdgård".
_NAME_MIN_WORDS_CHARS = 8
# Left over at the end of a name cut at a word boundary, such as the comma in "Runt Årsta, 2".
_NAME_TRAILING = " ,;:-–—/&+"

# Course times are made up from these, since a planned route has not been run: a watch racing a
# course's virtual partner paces the user at them. Metres per second.
REFERENCE_SPEED_M_S: dict[Activity, float] = {
    "running": 1000 / 360,  # 6:00 per km
    "cycling": 20 / 3.6,  # 20 km/h
}

# A roundabout exit within this many degrees of straight on is shown as straight on, the same band
# below which routing.instructions calls no turn at all (its `slight` setting).
ROUNDABOUT_STRAIGHT_DEG = 25

# Instruction maneuvers with a course point type of the same name.
_TURNS = {"slight_left", "left", "sharp_left", "slight_right", "right", "sharp_right", "u_turn"}

_MESG_NUM: dict[str, int] = Profile["mesg_num"]
# Semicircles are FIT's unit of latitude and longitude: 2^31 of them make 180 degrees.
_SEMICIRCLES_PER_DEG = 2**31 / 180


@dataclass(frozen=True, slots=True)
class CoursePoint:
    """A point of the route's line."""

    lon: float
    lat: float
    # along the line from its start
    distance_m: float
    altitude_m: float | None


@dataclass(frozen=True, slots=True)
class CourseTurn:
    """An instruction, at the point of the line with index `point`."""

    point: int
    maneuver: str
    # the overall turn, negative to the left
    angle: int
    label: str | None


@dataclass(frozen=True, slots=True)
class Course:
    route_id: int
    name: str
    activity: Activity
    points: Sequence[CoursePoint]
    turns: Sequence[CourseTurn]


def course_name(name: str) -> str:
    """The name in at most NAME_MAX_CHARS characters, cut after a whole word where one ends far
    enough in."""
    name = " ".join(name.split())
    if len(name) <= NAME_MAX_CHARS:
        return name
    # A space just past the limit ends the last whole word that fits.
    cut = name.rfind(" ", 0, NAME_MAX_CHARS + 1)
    words = name[: max(cut, 0)].rstrip(_NAME_TRAILING)
    if len(words) >= _NAME_MIN_WORDS_CHARS:
        return words
    return name[:NAME_MAX_CHARS].rstrip()


def course_point_type(maneuver: str, angle: int) -> str:
    """The FIT course point type a watch draws as the instruction's arrow. A roundabout becomes
    the way its exit goes."""
    if maneuver in _TURNS:
        return maneuver
    if maneuver == "roundabout":
        if abs(angle) < ROUNDABOUT_STRAIGHT_DEG:
            return "straight"
        return "left" if angle < 0 else "right"
    raise ValueError(f"unknown maneuver {maneuver!r}")


def encode_course(course: Course, created: datetime) -> bytes:
    """The course as a FIT file, timed from `created` at the activity's reference speed.

    Every course point takes the time and distance of the record at its point, so a watch counts
    down to it along the same line.
    """
    if not course.points:
        raise ValueError("a course needs points")
    start = created.replace(microsecond=0)
    speed = REFERENCE_SPEED_M_S[course.activity]
    times = [start + timedelta(seconds=round(p.distance_m / speed)) for p in course.points]
    first, last = course.points[0], course.points[-1]
    end = times[-1]

    fit = Encoder()
    _file_id(fit, serial_number=course.route_id % 2**32 or 1, time_created=start)
    _course(fit, name=course_name(course.name), sport=course.activity)
    _lap(fit, start=start, end=end, first=first, last=last)
    _event(fit, timestamp=start, event_type="start")
    for point, time in zip(course.points, times, strict=True):
        _record(fit, timestamp=time, point=point)
    for turn in course.turns:
        _course_point(
            fit,
            timestamp=times[turn.point],
            point=course.points[turn.point],
            point_type=course_point_type(turn.maneuver, turn.angle),
            name=(turn.label or "")[:NAME_MAX_CHARS].rstrip() or None,
        )
    _event(fit, timestamp=end, event_type="stop_disable_all")
    return fit.close()


def _semicircles(degrees: float) -> int:
    return round(degrees * _SEMICIRCLES_PER_DEG)


def _write(fit: Encoder, mesg: str, fields: dict[str, Any]) -> None:
    fit.on_mesg(_MESG_NUM[mesg], fields)


def _file_id(fit: Encoder, *, serial_number: int, time_created: datetime) -> None:
    # A course made by an app rather than a device. Garmin Connect tells files apart by maker,
    # product, serial number and time, so the route id stands in for the serial number.
    _write(
        fit,
        "FILE_ID",
        {
            "type": "course",
            "manufacturer": "development",
            "product": 0,
            "serial_number": serial_number,
            "time_created": time_created,
        },
    )


def _course(fit: Encoder, *, name: str, sport: Activity) -> None:
    _write(fit, "COURSE", {"sport": sport, "name": name})


def _lap(
    fit: Encoder, *, start: datetime, end: datetime, first: CoursePoint, last: CoursePoint
) -> None:
    seconds = (end - start).total_seconds()
    _write(
        fit,
        "LAP",
        {
            "timestamp": end,
            "start_time": start,
            "start_position_lat": _semicircles(first.lat),
            "start_position_long": _semicircles(first.lon),
            "end_position_lat": _semicircles(last.lat),
            "end_position_long": _semicircles(last.lon),
            "total_elapsed_time": seconds,
            "total_timer_time": seconds,
            "total_distance": last.distance_m,
        },
    )


def _event(fit: Encoder, *, timestamp: datetime, event_type: str) -> None:
    _write(
        fit,
        "EVENT",
        {"timestamp": timestamp, "event": "timer", "event_type": event_type, "event_group": 0},
    )


def _record(fit: Encoder, *, timestamp: datetime, point: CoursePoint) -> None:
    # The SDK leaves out a field that is None, which here is the altitude of a route without
    # heights.
    _write(
        fit,
        "RECORD",
        {
            "timestamp": timestamp,
            "position_lat": _semicircles(point.lat),
            "position_long": _semicircles(point.lon),
            "distance": point.distance_m,
            "altitude": point.altitude_m,
        },
    )


def _course_point(
    fit: Encoder, *, timestamp: datetime, point: CoursePoint, point_type: str, name: str | None
) -> None:
    _write(
        fit,
        "COURSE_POINT",
        {
            "timestamp": timestamp,
            "position_lat": _semicircles(point.lat),
            "position_long": _semicircles(point.lon),
            "distance": point.distance_m,
            "type": point_type,
            "name": name,
        },
    )
