"""
Scores graph edges against attribute layers. Triggers on raw queue changed elements; the enricher
rebuilds the affected features and rescores the edges near them. Runs in its own process.
"""

from .attributes import AreaShare, Attribute
from .definitions import ATTRIBUTES, GREEN, LAYERS, PARKS
from .enricher import BatchResult, EnrichResult, enrich_pending

__all__ = [
    "ATTRIBUTES",
    "GREEN",
    "LAYERS",
    "PARKS",
    "AreaShare",
    "Attribute",
    "BatchResult",
    "EnrichResult",
    "enrich_pending",
]
