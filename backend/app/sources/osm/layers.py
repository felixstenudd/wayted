"""
The layers fetched from OSM. Each is its own download with its own tiles in raw.fetched_tiles;
they share a request only because OSM happens to provide all of them.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OsmLayer:
    code: str  # a ref.source_layers code
    selectors: tuple[str, ...]  # Overpass selectors, without a bbox
    # Areas can cover a whole request rectangle without their outline touching it, so they are
    # also looked up by the rectangle's centre.
    is_area: bool = False


### Main Layer ###
ROADS = OsmLayer(code="roads", selectors=('way["highway"]',))

### Attribute layers ###
PARKS = OsmLayer(
    code="parks",
    selectors=('way["leisure"="park"]', 'relation["leisure"="park"]["type"="multipolygon"]'),
    is_area=True,
)
