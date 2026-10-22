from datetime import UTC, datetime, timedelta

import pytest
from garmin_fit_sdk import Decoder, Stream

from app.logbook.routes.fit import (
    Activity,
    Course,
    CoursePoint,
    CourseTurn,
    course_name,
    course_point_type,
    encode_course,
)

CREATED = datetime(2026, 10, 22, 7, 30, 15, 500_000, tzinfo=UTC)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Morning loop", "Morning loop"),
        ("Exactly fifteen", "Exactly fifteen"),
        # A space just past the limit: every word fits.
        ("Runt Årstaviken varv", "Runt Årstaviken"),
        ("Morning loop around Årsta", "Morning loop"),
        # What a cut at a word boundary leaves at the end is trimmed.
        ("Runt sjön, två varv", "Runt sjön, två"),
        ("Långa rundan, del 2", "Långa rundan"),
        # Too little before the last word boundary, or none: cut mid-word.
        ("A Kungsträdgårdsgatan", "A Kungsträdgård"),
        ("Kungsträdgårdsgatan", "Kungsträdgårdsg"),
        ("Hill   repeats   x10", "Hill repeats"),
    ],
)
def test_course_names_fit_a_watch(name: str, expected: str) -> None:
    assert course_name(name) == expected
    assert len(course_name(name)) <= 15


@pytest.mark.parametrize(
    ("maneuver", "angle", "expected"),
    [
        ("slight_left", -30, "slight_left"),
        ("left", -90, "left"),
        ("sharp_left", -140, "sharp_left"),
        ("slight_right", 30, "slight_right"),
        ("right", 90, "right"),
        ("sharp_right", 140, "sharp_right"),
        ("u_turn", 180, "u_turn"),
        ("roundabout", 0, "straight"),
        ("roundabout", -24, "straight"),
        ("roundabout", 24, "straight"),
        ("roundabout", -25, "left"),
        ("roundabout", -170, "left"),
        ("roundabout", 25, "right"),
        ("roundabout", 90, "right"),
    ],
)
def test_maneuvers_become_course_point_types(maneuver: str, angle: int, expected: str) -> None:
    assert course_point_type(maneuver, angle) == expected


def test_an_unknown_maneuver_has_no_course_point_type() -> None:
    with pytest.raises(ValueError, match="unknown maneuver"):
        course_point_type("depart", 0)


@pytest.mark.parametrize(("activity", "seconds"), [("running", 360), ("cycling", 180)])
def test_times_follow_the_reference_pace(activity: Activity, seconds: int) -> None:
    course = Course(
        route_id=1,
        name="Pace",
        activity=activity,
        points=[CoursePoint(18.0, 59.3, 0, None), CoursePoint(18.0, 59.309, 1000, None)],
        turns=[CourseTurn(1, "left", -90, "Storgatan")],
    )

    decoder = Decoder(Stream.from_byte_array(bytearray(encode_course(course, CREATED))))
    messages, errors = decoder.read()

    assert errors == []
    start = CREATED.replace(microsecond=0)
    assert [r["timestamp"] for r in messages["record_mesgs"]] == [
        start,
        start + timedelta(seconds=seconds),
    ]
    assert messages["lap_mesgs"][0]["total_timer_time"] == seconds
    assert messages["course_point_mesgs"][0]["timestamp"] == start + timedelta(seconds=seconds)
    assert messages["file_id_mesgs"][0]["time_created"] == start


def test_a_course_needs_points() -> None:
    with pytest.raises(ValueError, match="needs points"):
        encode_course(Course(1, "Empty", "running", [], []), CREATED)
