"""The layers and attributes the enricher builds and scores."""

from app.sources import osm

from .attributes import AreaShare, Attribute
from .layers import AreaLayer, FeatureLayer

# Built from the tags they are downloaded by, so the two lists cannot drift apart.
PARKS = AreaLayer(code=osm.PARKS.code, match=osm.PARKS.tags)
NATURAL_LAND = AreaLayer(code=osm.NATURE.code, match=osm.NATURE.tags)
WATER_AREAS = AreaLayer(code=osm.WATER.code, match=osm.WATER.tags)

# Kept apart: parks suit a city run, natural land a trail run.
GREEN = AreaShare(key="green", layers=(PARKS,), radius_m=25)
NATURE = AreaShare(key="nature", layers=(NATURAL_LAND,), radius_m=25)

LAYERS: tuple[FeatureLayer, ...] = (PARKS, NATURAL_LAND, WATER_AREAS)
ATTRIBUTES: tuple[Attribute, ...] = (GREEN, NATURE)
