"""The layers and attributes the enricher builds and scores."""

from .layers import AreaLayer, FeatureLayer

PARKS = AreaLayer(code="parks", match=({"leisure": "park"},))

LAYERS: tuple[FeatureLayer, ...] = (PARKS,)
