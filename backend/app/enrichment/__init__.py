"""
Scores graph edges against attribute layers. Triggers on raw queue changed elements; the enricher
rebuilds the affected features and rescores the edges near them. Runs in its own process.
"""

from .attributes import AreaShare, Attribute, Proximity
from .definitions import (
    ATTRIBUTES,
    GREEN,
    LAYERS,
    NATURAL_LAND,
    NATURE,
    PARKS,
    WATER_AREAS,
    WATER_LINES,
)
from .enricher import BatchResult, EnrichResult, enrich_pending
from .layers import LineLayer

__all__ = [
    "ATTRIBUTES",
    "GREEN",
    "LAYERS",
    "NATURAL_LAND",
    "NATURE",
    "PARKS",
    "WATER",
    "WATER_AREAS",
    "WATER_LINES",
    "AreaShare",
    "Attribute",
    "BatchResult",
    "EnrichResult",
    "LineLayer",
    "Proximity",
    "enrich_pending",
]
