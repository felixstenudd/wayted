"""A street grid written into raw, for planning routes on."""

from ..graph.raw_data import ORIGIN_LAT, ORIGIN_LON, STEP, Conn, add_line

# Columns are two raw_data steps apart, so blocks are about 114 m by 111 m.
COLUMN_STEPS = 2
SIZE = 25


def node_id(column: int, row: int) -> int:
    return 10_000 + row * 100 + column


def grid_point(column: float, row: float) -> str:
    """EWKT of a point on the grid, for passing to routing functions."""
    return f"SRID=4326;POINT({ORIGIN_LON + column * COLUMN_STEPS * STEP} {ORIGIN_LAT + row * STEP})"


async def add_grid(
    conn: Conn, tags: dict[str, str], one_way_rows: frozenset[int] = frozenset()
) -> None:
    """SIZE x SIZE crossings joined by a street per row (ways 1..) and column (ways 101..).
    Rows in one_way_rows are one-way eastwards."""
    for row in range(SIZE):
        points = [(node_id(c, row), c * COLUMN_STEPS, row) for c in range(SIZE)]
        row_tags = {**tags, "oneway": "yes"} if row in one_way_rows else tags
        await add_line(conn, 1 + row, points, row_tags)
    for column in range(SIZE):
        points = [(node_id(column, r), column * COLUMN_STEPS, r) for r in range(SIZE)]
        await add_line(conn, 101 + column, points, tags)
