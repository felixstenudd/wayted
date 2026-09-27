"""Tile and geographic area utilities."""

from collections.abc import Collection
from dataclasses import dataclass
from math import asinh, atan, ceil, degrees, floor, pi, radians, sinh, tan

MAX_LATITUDE = 85.0511287798
MAX_ZOOM = 22

EDGE_TOLERANCE = 1e-9


@dataclass(frozen=True, slots=True)
class Bounds:
    """
    A geographic bounding box in WGS84 coordinates.

    (west, south, east, north) (min_lon, min_lat, max_lon, max_lat)
    """

    west: float
    south: float
    east: float
    north: float


def _check_grid(z: int, *coords: int) -> None:
    if not 0 <= z <= MAX_ZOOM:
        raise ValueError(f"Zoom {z} is outside 0..{MAX_ZOOM}.")
    n = 1 << z
    for c in coords:
        if not 0 <= c < n:
            raise ValueError(f"Tile coordinate {c} is outside 0..{n - 1} at zoom {z}.")


def _x_position(lon: float, z: int) -> float:
    """Position in tile units from the west edge of the world."""
    return (lon + 180.0) / 360.0 * (1 << z)


def _y_position(lat: float, z: int) -> float:
    """Position in tile units from the north edge of the world."""
    return (1.0 - asinh(tan(radians(lat))) / pi) / 2.0 * (1 << z)


def _check_coordinate(lat: float, lon: float) -> None:
    if not -MAX_LATITUDE <= lat <= MAX_LATITUDE:
        raise ValueError("Latitude is outside Web Mercator limits.")
    if not -180.0 <= lon <= 180.0:
        raise ValueError("Longitude is outside -180..180.")


@dataclass(frozen=True, slots=True)
class Tile:
    """An XYZ Web Mercator tile."""

    x: int
    y: int
    z: int

    def __post_init__(self) -> None:
        _check_grid(self.z, self.x, self.y)

    @property
    def bounds(self) -> Bounds:
        """Return the geographic bounds of this tile."""
        n = 1 << self.z
        return Bounds(
            west=self.x / n * 360.0 - 180.0,
            south=degrees(atan(sinh(pi * (1 - 2 * (self.y + 1) / n)))),
            east=(self.x + 1) / n * 360.0 - 180.0,
            north=degrees(atan(sinh(pi * (1 - 2 * self.y / n)))),
        )

    @classmethod
    def from_lat_lon(cls, lat: float, lon: float, z: int) -> "Tile":
        """Return the tile containing a coordinate (latitude/longitude)."""
        _check_coordinate(lat, lon)
        n = 1 << z
        x = floor(_x_position(lon, z))
        y = floor(_y_position(lat, z))
        return cls(x=min(max(x, 0), n - 1), y=min(max(y, 0), n - 1), z=z)


@dataclass(frozen=True, slots=True)
class TileRect:
    """A rectangle of tiles at one zoom level. Max coordinates are inclusive."""

    z: int
    x_min: int
    y_min: int
    x_max: int
    y_max: int

    def __post_init__(self) -> None:
        _check_grid(self.z, self.x_min, self.y_min, self.x_max, self.y_max)
        if self.x_min > self.x_max or self.y_min > self.y_max:
            raise ValueError("Rectangle min coordinates must not exceed max coordinates.")

    @classmethod
    def of_tile(cls, tile: Tile) -> "TileRect":
        return cls(z=tile.z, x_min=tile.x, y_min=tile.y, x_max=tile.x, y_max=tile.y)

    @property
    def area(self) -> int:
        """Number of tiles in the rectangle."""
        return (self.x_max - self.x_min + 1) * (self.y_max - self.y_min + 1)

    @property
    def bounds(self) -> Bounds:
        north_west = Tile(x=self.x_min, y=self.y_min, z=self.z).bounds
        south_east = Tile(x=self.x_max, y=self.y_max, z=self.z).bounds
        return Bounds(
            west=north_west.west,
            south=south_east.south,
            east=south_east.east,
            north=north_west.north,
        )

    def tiles(self) -> set[Tile]:
        return {
            Tile(x=x, y=y, z=self.z)
            for x in range(self.x_min, self.x_max + 1)
            for y in range(self.y_min, self.y_max + 1)
        }

    def union(self, other: "TileRect") -> "TileRect":
        """Return the smallest rectangle containing both."""
        if other.z != self.z:
            raise ValueError("Rectangles must have the same zoom level.")
        return TileRect(
            z=self.z,
            x_min=min(self.x_min, other.x_min),
            y_min=min(self.y_min, other.y_min),
            x_max=max(self.x_max, other.x_max),
            y_max=max(self.y_max, other.y_max),
        )

    def overlap_area(self, other: "TileRect") -> int:
        """Return the number of tiles in both rectangles."""
        width = min(self.x_max, other.x_max) - max(self.x_min, other.x_min) + 1
        height = min(self.y_max, other.y_max) - max(self.y_min, other.y_min) + 1
        return max(width, 0) * max(height, 0)


def tiles_for_bounds(bounds: Bounds, z: int) -> set[Tile]:
    """
    Return all tiles intersecting a geographic bounding box.
    """
    if not -180.0 <= bounds.west <= bounds.east <= 180.0:
        raise ValueError("Bounds longitudes must satisfy -180 <= west <= east <= 180.")
    if bounds.south > bounds.north:
        raise ValueError("Bounds south must not be north of north.")
    # Tile edges at the top and bottom of the world lie a hair outside MAX_LATITUDE.
    north = min(bounds.north, MAX_LATITUDE)
    south = max(bounds.south, -MAX_LATITUDE)
    n = 1 << z
    x_min = floor(_x_position(bounds.west, z) + EDGE_TOLERANCE)
    y_min = floor(_y_position(north, z) + EDGE_TOLERANCE)
    x_max = ceil(_x_position(bounds.east, z) - EDGE_TOLERANCE) - 1
    y_max = ceil(_y_position(south, z) - EDGE_TOLERANCE) - 1
    rect = TileRect(
        z=z,
        x_min=min(max(x_min, 0), n - 1),
        y_min=min(max(y_min, 0), n - 1),
        x_max=min(max(x_max, x_min, 0), n - 1),
        y_max=min(max(y_max, y_min, 0), n - 1),
    )
    return rect.tiles()


def bounds_for_tiles(tiles: Collection[Tile]) -> Bounds:
    """Return the smallest bounds containing all tiles."""
    if not tiles:
        raise ValueError("At least one tile is required.")

    zoom_levels = {tile.z for tile in tiles}
    if len(zoom_levels) != 1:
        raise ValueError("All tiles must have the same zoom level.")

    bounds = [tile.bounds for tile in tiles]
    return Bounds(
        west=min(b.west for b in bounds),
        south=min(b.south for b in bounds),
        east=max(b.east for b in bounds),
        north=max(b.north for b in bounds),
    )
