"""Tile math and the tile registry"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Tile:
    x: int
    y: int
    z: int
