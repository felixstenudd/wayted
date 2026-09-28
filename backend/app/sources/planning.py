"""Groups requested tiles into as few request rectangles as the caps allow."""

import heapq
from collections import defaultdict
from collections.abc import Collection, Iterator
from itertools import count

from .tiles import Tile, TileRect

# Rectangles as plain (x_min, y_min, x_max, y_max) tuples while planning; creating a validated
# TileRect per candidate pair costs more than the planning itself.
type Rect = tuple[int, int, int, int]
type Entry = tuple[int, int, tuple[int, int, int, int], int, int]

# Side of a spatial index cell, in tiles.
CELL_SIZE = 8


def merge_cost(a: TileRect, b: TileRect) -> int:
    """Return the number of tiles fetched only because a and b are merged into one rectangle."""
    return a.union(b).area - (a.area + b.area - a.overlap_area(b))


def plan_rectangles(
    tiles: Collection[Tile], max_extra_tiles: int, max_tiles: int
) -> list[TileRect]:
    """
    Merge the tiles into rectangles, one request each.

    Two rectangles merge when the merge adds at most max_extra_tiles unrequested tiles and the
    result holds at most max_tiles tiles.
    """
    if max_extra_tiles < 0:
        raise ValueError("max_extra_tiles must be at least 0.")
    if max_tiles < 1:
        raise ValueError("max_tiles must be at least 1.")
    if not tiles:
        return []
    zooms = {tile.z for tile in tiles}
    if len(zooms) != 1:
        raise ValueError("All tiles must have the same zoom level.")

    planner = _Planner(max_extra_tiles, max_tiles)
    for tile in sorted(set(tiles), key=lambda t: (t.y, t.x)):
        planner.add((tile.x, tile.y, tile.x, tile.y))
    planner.merge_free()
    planner.merge_rest()
    (z,) = zooms
    return [
        TileRect(z=z, x_min=r[0], y_min=r[1], x_max=r[2], y_max=r[3])
        for r in sorted(planner.alive.values(), key=_key)
    ]


class _Planner:
    """
    The greedy merge in two phases, first merge tiles sharing a whole edge, then merge_rest only
    compares rectangles close enough for their union to fit max_tiles.
    """

    def __init__(self, max_extra_tiles: int, max_tiles: int) -> None:
        self.max_extra_tiles = max_extra_tiles
        self.max_tiles = max_tiles
        self.alive: dict[int, Rect] = {}
        self.ids = count()

    def add(self, rect: Rect) -> int:
        rect_id = next(self.ids)
        self.alive[rect_id] = rect
        return rect_id

    def merge_free(self) -> None:
        # Edge keys: where a neighbour's matching edge would be, with the span it must share.
        by_west: dict[tuple[int, int, int], int] = {}
        by_north: dict[tuple[int, int, int], int] = {}
        by_east: dict[tuple[int, int, int], int] = {}
        by_south: dict[tuple[int, int, int], int] = {}

        def index(rect_id: int, r: Rect) -> None:
            by_west[(r[0], r[1], r[3])] = rect_id
            by_east[(r[2], r[1], r[3])] = rect_id
            by_north[(r[1], r[0], r[2])] = rect_id
            by_south[(r[3], r[0], r[2])] = rect_id

        def unindex(r: Rect) -> None:
            del by_west[(r[0], r[1], r[3])]
            del by_east[(r[2], r[1], r[3])]
            del by_north[(r[1], r[0], r[2])]
            del by_south[(r[3], r[0], r[2])]

        heap: list[Entry] = []

        def push_neighbours(rect_id: int) -> None:
            r = self.alive[rect_id]
            neighbours = (
                by_west.get((r[2] + 1, r[1], r[3])),
                by_east.get((r[0] - 1, r[1], r[3])),
                by_north.get((r[3] + 1, r[0], r[2])),
                by_south.get((r[1] - 1, r[0], r[2])),
            )
            for other_id in neighbours:
                if other_id is None or other_id > rect_id:
                    continue
                union = _union(r, self.alive[other_id])
                area = _area(union)
                if area <= self.max_tiles:
                    heapq.heappush(heap, (0, area, _key(union), rect_id, other_id))

        for rect_id, r in self.alive.items():
            index(rect_id, r)
        for rect_id in list(self.alive):
            push_neighbours(rect_id)
        while heap:
            _, _, _, a_id, b_id = heapq.heappop(heap)
            if a_id not in self.alive or b_id not in self.alive:
                continue
            a, b = self.alive.pop(a_id), self.alive.pop(b_id)
            unindex(a)
            unindex(b)
            merged_id = self.add(_union(a, b))
            index(merged_id, self.alive[merged_id])
            push_neighbours(merged_id)

    def merge_rest(self) -> None:
        cells: dict[tuple[int, int], set[int]] = defaultdict(set)
        heap: list[Entry] = []

        def cells_of(x_min: int, y_min: int, x_max: int, y_max: int) -> Iterator[tuple[int, int]]:
            for cx in range(x_min // CELL_SIZE, x_max // CELL_SIZE + 1):
                for cy in range(y_min // CELL_SIZE, y_max // CELL_SIZE + 1):
                    yield cx, cy

        def push_pairs(rect_id: int) -> None:
            r = self.alive[rect_id]
            # The union is at least as tall and as wide as r and holds at most max_tiles tiles,
            # which bounds how far away a partner can lie.
            reach_x = self.max_tiles // (r[3] - r[1] + 1)
            reach_y = self.max_tiles // (r[2] - r[0] + 1)
            window = (
                r[2] - reach_x + 1,
                r[3] - reach_y + 1,
                r[0] + reach_x - 1,
                r[1] + reach_y - 1,
            )
            seen: set[int] = set()
            for cell in cells_of(*window):
                for other_id in cells.get(cell, ()):
                    if other_id >= rect_id or other_id in seen:
                        continue
                    seen.add(other_id)
                    other = self.alive[other_id]
                    union = _union(r, other)
                    area = _area(union)
                    if area > self.max_tiles:
                        continue
                    cost = area - (_area(r) + _area(other) - _overlap(r, other))
                    if cost <= self.max_extra_tiles:
                        heapq.heappush(heap, (cost, area, _key(union), rect_id, other_id))

        for rect_id, r in self.alive.items():
            for cell in cells_of(*r):
                cells[cell].add(rect_id)
        for rect_id in list(self.alive):
            push_pairs(rect_id)
        while heap:
            _, _, _, a_id, b_id = heapq.heappop(heap)
            if a_id not in self.alive or b_id not in self.alive:
                continue
            for old_id in (a_id, b_id):
                for cell in cells_of(*self.alive[old_id]):
                    cells[cell].discard(old_id)
            merged_id = self.add(_union(self.alive.pop(a_id), self.alive.pop(b_id)))
            for cell in cells_of(*self.alive[merged_id]):
                cells[cell].add(merged_id)
            push_pairs(merged_id)


def _area(r: Rect) -> int:
    return (r[2] - r[0] + 1) * (r[3] - r[1] + 1)


def _union(a: Rect, b: Rect) -> Rect:
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _overlap(a: Rect, b: Rect) -> int:
    width = min(a[2], b[2]) - max(a[0], b[0]) + 1
    height = min(a[3], b[3]) - max(a[1], b[1]) + 1
    return max(width, 0) * max(height, 0)


def _key(r: Rect) -> tuple[int, int, int, int]:
    return (r[1], r[0], r[3], r[2])
