"""Groups requested tiles into as few request rectangles as the caps allow."""

import heapq
from collections.abc import Collection
from itertools import count

from .tiles import Tile, TileRect


def merge_cost(a: TileRect, b: TileRect) -> int:
    """Return the number of tiles fetched only because a and b are merged into one rectangle."""
    return a.union(b).area - (a.area + b.area - a.overlap_area(b))


def _rect_key(rect: TileRect) -> tuple[int, int, int, int]:
    return (rect.y_min, rect.x_min, rect.y_max, rect.x_max)


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
    if len({tile.z for tile in tiles}) != 1:
        raise ValueError("All tiles must have the same zoom level.")

    alive: dict[int, TileRect] = {}
    ids = count()
    heap: list[tuple[int, int, tuple[int, int, int, int], int, int]] = []

    def push_pairs(new_id: int) -> None:
        new = alive[new_id]
        for other_id, other in alive.items():
            if other_id == new_id:
                continue
            union = new.union(other)
            cost = merge_cost(new, other)
            if cost <= max_extra_tiles and union.area <= max_tiles:
                heapq.heappush(heap, (cost, union.area, _rect_key(union), new_id, other_id))

    for tile in sorted(set(tiles), key=lambda t: (t.y, t.x)):
        tile_id = next(ids)
        alive[tile_id] = TileRect.of_tile(tile)
        push_pairs(tile_id)

    # Entries whose rectangles were merged away are skipped when popped.
    while heap:
        _, _, _, a_id, b_id = heapq.heappop(heap)
        if a_id not in alive or b_id not in alive:
            continue
        merged = alive.pop(a_id).union(alive.pop(b_id))
        merged_id = next(ids)
        alive[merged_id] = merged
        push_pairs(merged_id)

    return sorted(alive.values(), key=_rect_key)
