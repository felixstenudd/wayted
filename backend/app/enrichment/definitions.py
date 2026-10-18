"""The layers and attributes the enricher builds and scores."""

from .attributes import AreaShare, Attribute
from .layers import AreaLayer, FeatureLayer

PARKS = AreaLayer(code="parks", match=({"leisure": "park"},))

GREEN = AreaShare(key="green", layers=(PARKS,), radius_m=25)

LAYERS: tuple[FeatureLayer, ...] = (PARKS,)
ATTRIBUTES: tuple[Attribute, ...] = (GREEN,)
