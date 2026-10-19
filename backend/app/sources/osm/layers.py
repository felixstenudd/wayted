"""
The layers fetched from OSM. Each is its own download with its own tiles in raw.fetched_tiles;
they share a request only because OSM happens to provide all of them.
"""

from collections.abc import Sequence
from dataclasses import dataclass

# Tags an element must all carry, e.g. {"landuse": "forest"}.
type TagPattern = dict[str, str]


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
    # An area layer's tag patterns; the enricher builds its features from the same ones.
    tags: tuple[TagPattern, ...] = ()


def area_selectors(tags: Sequence[TagPattern]) -> tuple[str, ...]:
    """Ways and multipolygon relations with any of the patterns. Values of one key share a regex."""
    by_key: dict[str, list[str]] = {}
    several_keys: list[str] = []
    for pattern in tags:
        if len(pattern) == 1:
            [(key, value)] = pattern.items()
            by_key.setdefault(key, []).append(value)
        else:
            several_keys.append("".join(f'["{k}"="{v}"]' for k, v in pattern.items()))
    filters = [_one_key(key, values) for key, values in by_key.items()] + several_keys
    return tuple(f"way{f}" for f in filters) + tuple(
        f'relation{f}["type"="multipolygon"]' for f in filters
    )


def _one_key(key: str, values: list[str]) -> str:
    if len(values) == 1:
        return f'["{key}"="{values[0]}"]'
    return f'["{key}"~"^({"|".join(values)})$"]'


def area_layer(code: str, tags: tuple[TagPattern, ...]) -> OsmLayer:
    return OsmLayer(code=code, selectors=area_selectors(tags), is_area=True, tags=tags)


### Main Layer ###
ROADS = OsmLayer(
    code="roads",
    selectors=('way["highway"]', 'way["route"="ferry"]'),
    # Signed routes
    shallow_selectors=('relation["route"~"^(bicycle|foot|hiking|running|mtb)$"]',),
)

### Attribute layers ###
PARKS = area_layer("parks", ({"leisure": "park"},))

# Land left to grow: the opposite of a park, for runs out of the city.
NATURE = area_layer(
    "nature",
    (
        {"landuse": "forest"},
        {"natural": "wood"},
        {"natural": "scrub"},
        {"natural": "heath"},
        {"natural": "grassland"},
        {"landuse": "meadow"},
        {"natural": "wetland"},
        {"leisure": "nature_reserve"},
    ),
)

# Every layer available (that has a downloader)
LAYERS = (ROADS, PARKS, NATURE)
