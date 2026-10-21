"""The layers and attributes the enricher builds and scores."""

from app.sources import osm

from .attributes import AreaShare, Attribute, HeightChange
from .layers import AreaLayer, FeatureLayer

# Built from the tags they are downloaded by, so the two lists cannot drift apart.
PARKS = AreaLayer(code=osm.PARKS.code, match=osm.PARKS.tags)
NATURAL_LAND = AreaLayer(code=osm.NATURE.code, match=osm.NATURE.tags)

# Kept apart: parks suit a city run, natural land a trail run.
GREEN = AreaShare(key="green", layers=(PARKS,), radius_m=25)
NATURE = AreaShare(key="nature", layers=(NATURAL_LAND,), radius_m=25)

# Half a cell of the height model apart, each height the mean over a cross 120 m wide. The
# model sees roofs and treetops, and a narrower cross left Umeå's flat city centre full of steep
# edges; this one keeps it calm and still shows the streets down the river terrace. Without the
# smoothing, short edges scored nearly twice as hilly as long ones. A run or ride that climbs and
# drops 6 % of its length on average is as hilly as it gets. Starting values, to tune.
HILLS = HeightChange(
    key="hills",
    layers=(),
    sample_m=15,
    smooth_m=60,
    threshold_m=1.0,
    ends_m=0.5,
    full_grade=0.06,
)

LAYERS: tuple[FeatureLayer, ...] = (PARKS, NATURAL_LAND)
ATTRIBUTES: tuple[Attribute, ...] = (GREEN, NATURE, HILLS)
