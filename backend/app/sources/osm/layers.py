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
    # Fetched without their nodes or members, for relations whose members reach far outside the
    # rectangle.
    shallow_selectors: tuple[str, ...] = ()


### Main Layer ###
ROADS = OsmLayer(
    code="roads",
    selectors=('way["highway"]', 'way["route"="ferry"]'),
    # Signed routes
    shallow_selectors=('relation["route"~"^(bicycle|foot|hiking|running|mtb)$"]',),
)

### Attribute layers ###
PARKS = OsmLayer(
    code="parks",
    selectors=('way["leisure"="park"]', 'relation["leisure"="park"]["type"="multipolygon"]'),
    is_area=True,
)

# Land left to grow: the opposite of a park, for runs out of the city.
_NATURE_TAGS = (
    '["landuse"~"^(forest|meadow)$"]',
    '["natural"~"^(wood|scrub|heath|grassland|wetland)$"]',
    '["leisure"="nature_reserve"]',
)
NATURE = OsmLayer(
    code="nature",
    selectors=tuple(f"way{tags}" for tags in _NATURE_TAGS)
    + tuple(f'relation{tags}["type"="multipolygon"]' for tags in _NATURE_TAGS),
    is_area=True,
)

# Every layer available (that has a downloader)
LAYERS = (ROADS, PARKS, NATURE)
