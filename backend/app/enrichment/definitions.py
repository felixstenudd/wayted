"""The layers and attributes the enricher builds and scores."""

from .attributes import AreaShare, Attribute
from .layers import AreaLayer, FeatureLayer

PARKS = AreaLayer(code="parks", match=({"leisure": "park"},))
NATURAL_LAND = AreaLayer(
    code="nature",
    match=(
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

# Kept apart: parks suit a city run, natural land a trail run.
GREEN = AreaShare(key="green", layers=(PARKS,), radius_m=25)
NATURE = AreaShare(key="nature", layers=(NATURAL_LAND,), radius_m=25)

LAYERS: tuple[FeatureLayer, ...] = (PARKS, NATURAL_LAND)
ATTRIBUTES: tuple[Attribute, ...] = (GREEN, NATURE)
