import random

import pytest

from app.sources.tiles import (
    MAX_LATITUDE,
    Bounds,
    Tile,
    TileRect,
    bounds_for_tiles,
    tiles_for_bounds,
)


def block(x_min: int, y_min: int, x_max: int, y_max: int, z: int = 14) -> set[Tile]:
    return {Tile(x=x, y=y, z=z) for x in range(x_min, x_max + 1) for y in range(y_min, y_max + 1)}


def test_single_tile_round_trips() -> None:
    tile = Tile(x=8800, y=4700, z=14)
    assert tiles_for_bounds(bounds_for_tiles({tile}), 14) == {tile}


@pytest.mark.parametrize(
    "rect",
    [(8800, 4700, 8802, 4701), (0, 0, 3, 3), (16380, 16380, 16383, 16383), (0, 8190, 5, 8193)],
)
def test_block_round_trips(rect: tuple[int, int, int, int]) -> None:
    tiles = block(*rect)
    assert tiles_for_bounds(bounds_for_tiles(tiles), 14) == tiles


def test_every_zoom_round_trips_at_world_corners() -> None:
    for z in range(0, 23):
        n = 2**z
        for tile in {Tile(x=0, y=0, z=z), Tile(x=n - 1, y=n - 1, z=z)}:
            assert tiles_for_bounds(tile.bounds, z) == {tile}


@pytest.mark.parametrize("z", range(0, 23))
def test_random_tiles_round_trip_at_every_zoom(z: int) -> None:
    rng = random.Random(z)
    n = 1 << z
    for _ in range(500):
        tile = Tile(x=rng.randrange(n), y=rng.randrange(n), z=z)
        assert tiles_for_bounds(tile.bounds, z) == {tile}


def test_random_blocks_round_trip_at_the_highest_zoom() -> None:
    rng = random.Random(22)
    n = 1 << 22
    for _ in range(200):
        x, y = rng.randrange(n - 4), rng.randrange(n - 4)
        tiles = block(x, y, x + rng.randrange(4), y + rng.randrange(4), z=22)
        assert tiles_for_bounds(bounds_for_tiles(tiles), 22) == tiles


def test_bounds_inside_one_tile_give_that_tile() -> None:
    b = Tile(x=8800, y=4700, z=14).bounds
    inner = Bounds(
        west=b.west + 0.001, south=b.south + 0.001, east=b.east - 0.001, north=b.north - 0.001
    )
    assert tiles_for_bounds(inner, 14) == {Tile(x=8800, y=4700, z=14)}


def test_bounds_crossing_an_edge_include_both_tiles() -> None:
    b = Tile(x=8800, y=4700, z=14).bounds
    crossing = Bounds(west=b.west, south=b.south, east=b.east + 0.001, north=b.north)
    assert tiles_for_bounds(crossing, 14) == {
        Tile(x=8800, y=4700, z=14),
        Tile(x=8801, y=4700, z=14),
    }


def test_point_bounds_give_one_tile() -> None:
    point = Bounds(west=18.07, south=59.33, east=18.07, north=59.33)
    assert tiles_for_bounds(point, 14) == {Tile.from_lat_lon(lat=59.33, lon=18.07, z=14)}


@pytest.mark.parametrize(
    "bounds",
    [
        Bounds(west=10.0, south=59.0, east=9.0, north=60.0),
        Bounds(west=10.0, south=60.0, east=11.0, north=59.0),
        Bounds(west=-181.0, south=59.0, east=11.0, north=60.0),
    ],
)
def test_invalid_bounds_are_rejected(bounds: Bounds) -> None:
    with pytest.raises(ValueError):
        tiles_for_bounds(bounds, 14)


@pytest.mark.parametrize(
    ("x", "y", "z"), [(-1, 0, 3), (0, -1, 3), (8, 0, 3), (0, 8, 3), (0, 0, -1), (0, 0, 23)]
)
def test_tile_outside_grid_is_rejected(x: int, y: int, z: int) -> None:
    with pytest.raises(ValueError):
        Tile(x=x, y=y, z=z)


def test_from_lat_lon_rejects_longitude_out_of_range() -> None:
    with pytest.raises(ValueError):
        Tile.from_lat_lon(lat=59.0, lon=-190.0, z=14)


def test_from_lat_lon_rejects_latitude_out_of_range() -> None:
    with pytest.raises(ValueError):
        Tile.from_lat_lon(lat=86.0, lon=0.0, z=14)


def test_from_lat_lon_at_max_latitude_is_top_row() -> None:
    assert Tile.from_lat_lon(lat=MAX_LATITUDE, lon=0.0, z=14).y == 0


def test_from_lat_lon_at_east_edge_is_last_column() -> None:
    assert Tile.from_lat_lon(lat=0.0, lon=180.0, z=3).x == 7


def test_bounds_for_tiles_rejects_mixed_zoom() -> None:
    with pytest.raises(ValueError):
        bounds_for_tiles([Tile(x=0, y=0, z=1), Tile(x=0, y=0, z=2)])


def test_rect_area_and_tiles() -> None:
    rect = TileRect(z=14, x_min=10, y_min=20, x_max=12, y_max=21)
    assert rect.area == 6
    assert rect.tiles() == block(10, 20, 12, 21)


def test_rect_bounds_match_its_tiles() -> None:
    rect = TileRect(z=14, x_min=8800, y_min=4700, x_max=8802, y_max=4701)
    assert rect.bounds == bounds_for_tiles(rect.tiles())


def test_rect_union_and_overlap() -> None:
    a = TileRect(z=14, x_min=0, y_min=0, x_max=2, y_max=2)
    b = TileRect(z=14, x_min=2, y_min=1, x_max=4, y_max=1)
    assert a.union(b) == TileRect(z=14, x_min=0, y_min=0, x_max=4, y_max=2)
    assert a.overlap_area(b) == 1
    assert a.overlap_area(TileRect(z=14, x_min=5, y_min=5, x_max=5, y_max=5)) == 0


def test_rect_rejects_inverted_coordinates() -> None:
    with pytest.raises(ValueError):
        TileRect(z=14, x_min=3, y_min=0, x_max=2, y_max=0)
