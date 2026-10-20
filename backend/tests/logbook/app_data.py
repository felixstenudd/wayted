from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import TupleRow

type Conn = AsyncConnection[TupleRow]


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


async def add_edges(conn: Conn, count: int) -> list[int]:
    """A straight chain of `count` edges along one way, open to running and cycling both ways."""
    await conn.execute("INSERT INTO graph.ways (id, tags) VALUES (1, '{}')")
    await conn.execute(
        """
        INSERT INTO graph.vertices (id, geom)
        SELECT n, ST_SetSRID(ST_MakePoint(20.0 + n * 0.001, 63.8), 4326)
        FROM generate_series(0, %s) n
        """,
        (count,),
    )
    cur = await conn.execute(
        """
        INSERT INTO graph.edges
            (way_id, source, target, occurrence, geom, length_m, forward, backward)
        SELECT 1, n, n + 1, 1, ST_MakeLine(a.geom, b.geom), 50,
               '{running,cycling}', '{running,cycling}'
        FROM generate_series(0, %s - 1) n
        JOIN graph.vertices a ON a.id = n
        JOIN graph.vertices b ON b.id = n + 1
        ORDER BY n
        RETURNING id
        """,
        (count,),
    )
    return [row[0] for row in await cur.fetchall()]
