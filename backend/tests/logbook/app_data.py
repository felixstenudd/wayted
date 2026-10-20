import json
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import TupleRow

type Conn = AsyncConnection[TupleRow]
type LonLat = tuple[float, float]

BOTH = ("running", "cycling")


async def add_user(conn: Conn, email: str = "runner@example.com") -> UUID:
    cur = await conn.execute(
        """
        INSERT INTO app.users (email, name, password_hash) VALUES (%s, 'Runner', 'x')
        RETURNING id
        """,
        (email,),
    )
    row = await cur.fetchone()
    assert row is not None
    user_id: UUID = row[0]
    return user_id


async def add_edge(
    conn: Conn,
    source: int,
    target: int,
    coords: list[LonLat],
    *,
    length_m: float = 50,
    forward: tuple[str, ...] = BOTH,
    backward: tuple[str, ...] = BOTH,
    scores: dict[str, float] | None = None,
) -> int:
    """An edge through `coords`, adding its way and end vertices when missing."""
    await conn.execute("INSERT INTO graph.ways (id, tags) VALUES (1, '{}') ON CONFLICT DO NOTHING")
    for vertex_id, (lon, lat) in ((source, coords[0]), (target, coords[-1])):
        await conn.execute(
            """
            INSERT INTO graph.vertices (id, geom)
            VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
            ON CONFLICT DO NOTHING
            """,
            (vertex_id, lon, lat),
        )
    line = "LINESTRING(" + ", ".join(f"{lon} {lat}" for lon, lat in coords) + ")"
    cur = await conn.execute(
        """
        INSERT INTO graph.edges
            (way_id, source, target, occurrence, geom, length_m, forward, backward, scores)
        VALUES (1, %s, %s, 1, ST_GeomFromText(%s, 4326), %s, %s, %s, %s)
        RETURNING id
        """,
        (source, target, line, length_m, list(forward), list(backward), json.dumps(scores or {})),
    )
    row = await cur.fetchone()
    assert row is not None
    edge_id: int = row[0]
    return edge_id


async def add_edges(conn: Conn, count: int) -> list[int]:
    """A straight chain of `count` edges, open to running and cycling both ways."""
    return [
        await add_edge(conn, n, n + 1, [(20.0 + n * 0.001, 63.8), (20.001 + n * 0.001, 63.8)])
        for n in range(count)
    ]
