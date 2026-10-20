import pytest

from ..graph.raw_data import Conn, add_line, add_way
from .area_data import Pool, run, scores

pytestmark = pytest.mark.db

SURFACES = [
    *[(s, 1.0) for s in ("asphalt", "concrete", "concrete:plates", "paved", "chipseal")],
    *[(s, 0.8) for s in ("paving_stones", "concrete:lanes", "wood", "metal")],
    *[(s, 0.6) for s in ("sett", "cobblestone", "unhewn_cobblestone")],
    *[(s, 0.5) for s in ("compacted", "fine_gravel")],
    *[(s, 0.4) for s in ("gravel", "pebblestone", "unpaved")],
    *[(s, 0.2) for s in ("ground", "dirt", "earth", "woodchips")],
    *[(s, 0.1) for s in ("grass", "sand", "mud", "rock")],
]

HIGHWAYS = [
    *[
        (h, 1.0)
        for h in (
            "primary",
            "primary_link",
            "secondary",
            "secondary_link",
            "tertiary",
            "tertiary_link",
            "unclassified",
            "residential",
            "living_street",
            "service",
            "cycleway",
        )
    ],
    *[(h, 0.8) for h in ("footway", "pedestrian", "steps")],
    *[(h, 0.3) for h in ("path", "bridleway")],
]


async def prepared(
    conn: Conn, tags: dict[str, str], mapper_pool: Pool, enricher_pool: Pool
) -> object:
    await add_line(conn, 1, [(1, 0, 0), (2, 1, 0)], tags)
    await run(mapper_pool, enricher_pool)
    return (await scores(conn))[1].get("prepared")


@pytest.mark.parametrize(("surface", "expected"), SURFACES)
async def test_surface_gives_its_step(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool, surface: str, expected: float
) -> None:
    tags = {"highway": "path", "surface": surface}
    assert await prepared(admin_conn, tags, mapper_pool, enricher_pool) == expected


@pytest.mark.parametrize(("highway", "expected"), HIGHWAYS)
async def test_untagged_way_is_guessed_from_the_highway(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool, highway: str, expected: float
) -> None:
    tags = {"highway": highway}
    assert await prepared(admin_conn, tags, mapper_pool, enricher_pool) == expected


async def test_surface_beats_the_highway(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    tags = {"highway": "residential", "surface": "gravel"}
    assert await prepared(admin_conn, tags, mapper_pool, enricher_pool) == 0.4


async def test_unrecognised_surface_falls_back_to_the_highway(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    tags = {"highway": "path", "surface": "foo"}
    assert await prepared(admin_conn, tags, mapper_pool, enricher_pool) == 0.3


@pytest.mark.parametrize(
    ("tracktype", "expected"),
    [("grade1", 1.0), ("grade2", 0.5), ("grade3", 0.4), ("grade4", 0.2), ("grade5", 0.1)],
)
async def test_track_is_guessed_by_tracktype(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool, tracktype: str, expected: float
) -> None:
    tags = {"highway": "track", "tracktype": tracktype}
    assert await prepared(admin_conn, tags, mapper_pool, enricher_pool) == expected


@pytest.mark.parametrize("tags", [{"highway": "track"}, {"highway": "track", "tracktype": "x"}])
async def test_track_without_a_known_tracktype_is_a_middle_guess(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool, tags: dict[str, str]
) -> None:
    assert await prepared(admin_conn, tags, mapper_pool, enricher_pool) == 0.4


async def test_ferry_has_no_prepared_score(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_line(admin_conn, 1, [(1, 0, 0), (2, 1, 0)], {"route": "ferry"})
    await run(mapper_pool, enricher_pool)

    assert "prepared" not in (await scores(admin_conn))[1]


async def test_retagging_to_unknown_removes_the_score(
    admin_conn: Conn, mapper_pool: Pool, enricher_pool: Pool
) -> None:
    await add_line(admin_conn, 1, [(1, 0, 0), (2, 1, 0)], {"highway": "path", "surface": "asphalt"})
    await run(mapper_pool, enricher_pool)

    await add_way(admin_conn, 1, [1, 2], {"route": "ferry"})
    await run(mapper_pool, enricher_pool)

    assert "prepared" not in (await scores(admin_conn))[1]
