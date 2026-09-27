"""Tile and geographic area utilities."""

from dataclasses import dataclass
from math import atan, asinh, degrees, floor, pi, radians, sinh, tan


MAX_LATITUDE = 85.0511287798


@dataclass(frozen=True, slots=True)
class Bounds:
    """
    A geographic bounding box in WGS84 coordinates.
    
    (west, south, east, north) (min_long, min_lat, max_long, max_lat)
	
	Coordinates are longitude/latitude in WGS84.
    """

    west: float
    south: float
    east: float
    north: float


@dataclass(frozen=True, slots=True)
class Tile:
    """An XYZ Web Mercator tile."""

    x: int
    y: int
    z: int

    @property
    def bounds(self) -> Bounds:
        """Return the geographic bounds of this tile."""

        n = 2**self.z

        west = self.x / n * 360.0 - 180.0
        east = (self.x + 1) / n * 360.0 - 180.0

        north = degrees(
            atan(sinh(pi * (1 - 2 * self.y / n)))
        )

        south = degrees(
            atan(sinh(pi * (1 - 2 * (self.y + 1) / n)))
        )

        return Bounds(
            west=west,
            south=south,
            east=east,
            north=north,
        )

    @classmethod
    def from_lat_lon(
        cls,
        lat: float,
        lon: float,
        z: int,
    ) -> "Tile":
        """Return the tile containing a coordinate (latitude/longitude)."""

        if not -MAX_LATITUDE <= lat <= MAX_LATITUDE:
            raise ValueError("Latitude is outside Web Mercator limits.")

        n = 2**z

        x = floor((lon + 180.0) / 360.0 * n)

        lat_rad = radians(lat)

        y = floor(
            (
                1.0 - asinh(tan(lat_rad)) / pi
            )
            / 2.0
            * n
        )

        x = min(x, n - 1)
        y = min(y, n - 1)

        return cls(x=x, y=y, z=z)


def tiles_for_bounds(
    bounds: Bounds,
    z: int,
) -> set[Tile]:
    """Return all tiles intersecting a geographic bounding box."""

    top_left = Tile.from_lat_lon(
        bounds.north,
        bounds.west,
        z,
    )

    bottom_right = Tile.from_lat_lon(
        bounds.south,
        bounds.east,
        z,
    )

    return {
        Tile(x=x, y=y, z=z)
        for x in range(top_left.x, bottom_right.x + 1)
        for y in range(top_left.y, bottom_right.y + 1)
    }

def bounds_for_tiles(tiles: set[Tile]) -> Bounds:
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