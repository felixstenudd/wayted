import random

import pytest

from app.sources.planning import merge_cost, plan_rectangles
from app.sources.tiles import Tile, TileRect


def block(x_min: int, y_min: int, x_max: int, y_max: int, z: int = 14) -> set[Tile]:
    return {Tile(x=x, y=y, z=z) for x in range(x_min, x_max + 1) for y in range(y_min, y_max + 1)}


def covered(rects: list[TileRect]) -> set[Tile]:
    return set().union(*(r.tiles() for r in rects))


def test_empty_input_plans_nothing() -> None:
    assert plan_rectangles([], max_extra_tiles=0, max_tiles=64) == []


def test_solid_block_is_one_rectangle_without_extra_budget() -> None:
    rects = plan_rectangles(block(0, 0, 3, 2), max_extra_tiles=0, max_tiles=64)
    assert rects == [TileRect(z=14, x_min=0, y_min=0, x_max=3, y_max=2)]


def test_merge_cost_counts_only_gap_tiles() -> None:
    a = TileRect(z=14, x_min=0, y_min=0, x_max=1, y_max=1)
    b = TileRect(z=14, x_min=4, y_min=0, x_max=5, y_max=1)
    assert merge_cost(a, b) == 4


def test_clusters_merge_when_gap_is_within_budget() -> None:
    tiles = block(0, 0, 1, 1) | block(4, 0, 5, 1)  # gap of 2 columns x 2 rows = 4 tiles
    rects = plan_rectangles(tiles, max_extra_tiles=4, max_tiles=64)
    assert rects == [TileRect(z=14, x_min=0, y_min=0, x_max=5, y_max=1)]


def test_clusters_stay_apart_when_gap_exceeds_budget() -> None:
    tiles = block(0, 0, 1, 1) | block(4, 0, 5, 1)
    rects = plan_rectangles(tiles, max_extra_tiles=3, max_tiles=64)
    assert rects == [
        TileRect(z=14, x_min=0, y_min=0, x_max=1, y_max=1),
        TileRect(z=14, x_min=4, y_min=0, x_max=5, y_max=1),
    ]


def test_no_rectangle_exceeds_max_tiles() -> None:
    tiles = block(0, 0, 9, 9)
    rects = plan_rectangles(tiles, max_extra_tiles=0, max_tiles=16)
    assert all(r.area <= 16 for r in rects)
    assert covered(rects) == tiles


def test_large_area_with_budget_is_still_capped_and_covered() -> None:
    tiles = block(0, 0, 19, 19)
    rects = plan_rectangles(tiles, max_extra_tiles=16, max_tiles=64)
    assert all(r.area <= 64 for r in rects)
    assert covered(rects) >= tiles


def test_l_shape_needs_budget_for_the_corner() -> None:
    tiles = {Tile(x=0, y=0, z=14), Tile(x=1, y=0, z=14), Tile(x=0, y=1, z=14)}
    assert len(plan_rectangles(tiles, max_extra_tiles=0, max_tiles=64)) == 2
    assert plan_rectangles(tiles, max_extra_tiles=1, max_tiles=64) == [
        TileRect(z=14, x_min=0, y_min=0, x_max=1, y_max=1)
    ]


def test_output_does_not_depend_on_input_order() -> None:
    tiles = list(block(0, 0, 5, 5) | block(9, 2, 11, 4) | {Tile(x=20, y=20, z=14)})
    expected = plan_rectangles(tiles, max_extra_tiles=6, max_tiles=24)
    for seed in range(5):
        random.Random(seed).shuffle(tiles)
        assert plan_rectangles(tiles, max_extra_tiles=6, max_tiles=24) == expected


def test_mixed_zoom_is_rejected() -> None:
    with pytest.raises(ValueError):
        plan_rectangles(
            [Tile(x=0, y=0, z=13), Tile(x=0, y=0, z=14)], max_extra_tiles=0, max_tiles=64
        )


@pytest.mark.parametrize(("extra", "max_tiles"), [(-1, 64), (0, 0)])
def test_invalid_caps_are_rejected(extra: int, max_tiles: int) -> None:
    with pytest.raises(ValueError):
        plan_rectangles([Tile(x=0, y=0, z=14)], max_extra_tiles=extra, max_tiles=max_tiles)


def test_duplicate_tiles_are_planned_once() -> None:
    tile = Tile(x=5, y=5, z=14)
    assert plan_rectangles([tile, tile], max_extra_tiles=0, max_tiles=64) == [
        TileRect.of_tile(tile)
    ]
