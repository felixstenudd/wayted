import pytest
from psycopg_pool import AsyncConnectionPool

from app.graph import map_pending

from .raw_data import Conn, add_node, add_way

pytestmark = pytest.mark.db

Pool = AsyncConnectionPool[Conn]
BOTH = ["cycling", "running"]
RUNNING = ["running"]
CYCLING = ["cycling"]


async def access_for(
    conn: Conn, pool: Pool, tags: dict[str, str], closed: bool = False
) -> tuple[list[str], list[str]] | None:
    """(forward, backward) of the one edge a way with these tags becomes, or None if skipped."""
    for node_id, x, y in [(1, 0, 0), (2, 1, 0), (3, 1, 1)]:
        await add_node(conn, node_id, x, y)
    await add_way(conn, 1, [1, 2, 3, 1] if closed else [1, 2, 3], tags)
    await map_pending(pool)
    cur = await conn.execute("SELECT forward, backward FROM graph.edges")
    rows = await cur.fetchall()
    assert len(rows) <= 1
    return (rows[0][0], rows[0][1]) if rows else None


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        ({"highway": "residential"}, (BOTH, BOTH)),
        ({"highway": "footway"}, (RUNNING, RUNNING)),
        ({"highway": "motorway"}, None),
        ({"highway": "construction"}, None),
        ({"route": "ferry"}, (BOTH, BOTH)),
        ({"highway": "residential", "oneway": "yes"}, (BOTH, RUNNING)),
        ({"highway": "residential", "oneway": "-1"}, (RUNNING, BOTH)),
        ({"highway": "residential", "oneway": "no"}, (BOTH, BOTH)),
        ({"highway": "residential", "oneway": "reversible"}, (BOTH, BOTH)),
        ({"highway": "footway", "oneway": "yes"}, (RUNNING, RUNNING)),
        ({"highway": "residential", "oneway": "yes", "oneway:bicycle": "no"}, (BOTH, BOTH)),
        ({"highway": "footway", "oneway:foot": "yes"}, (RUNNING, [])),
        ({"highway": "footway", "bicycle": "designated"}, (BOTH, BOTH)),
        ({"highway": "cycleway", "foot": "no"}, (CYCLING, CYCLING)),
        ({"highway": "residential", "access": "private"}, None),
        ({"highway": "residential", "access": "no", "foot": "yes"}, (RUNNING, RUNNING)),
        ({"highway": "primary", "bicycle": "use_sidepath"}, (RUNNING, RUNNING)),
    ],
)
async def test_tags_decide_who_may_go_which_way(
    admin_conn: Conn,
    mapper_pool: Pool,
    tags: dict[str, str],
    expected: tuple[list[str], list[str]] | None,
) -> None:
    assert await access_for(admin_conn, mapper_pool, tags) == expected


async def test_roundabout_is_one_way_for_cycling(admin_conn: Conn, mapper_pool: Pool) -> None:
    tags = {"highway": "residential", "junction": "roundabout"}

    assert await access_for(admin_conn, mapper_pool, tags, closed=True) == (BOTH, RUNNING)


async def test_highway_area_is_skipped(admin_conn: Conn, mapper_pool: Pool) -> None:
    tags = {"highway": "pedestrian", "area": "yes"}

    assert await access_for(admin_conn, mapper_pool, tags, closed=True) is None
