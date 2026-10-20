"""The layers and attributes the enricher builds and scores."""

from app.sources import osm

from .attributes import AreaShare, Attribute, Proximity, SurfaceScore
from .layers import AreaLayer, FeatureLayer, LineLayer

# Built from the tags they are downloaded by, so the two lists cannot drift apart.
PARKS = AreaLayer(code=osm.PARKS.code, match=osm.PARKS.tags)
NATURAL_LAND = AreaLayer(code=osm.NATURE.code, match=osm.NATURE.tags)
WATER_AREAS = AreaLayer(code=osm.WATER.code, match=osm.WATER.tags)
WATER_LINES = LineLayer(code=osm.WATER_LINES.code, match=osm.WATER_LINES.tags)

# Kept apart: parks suit a city run, natural land a trail run.
GREEN = AreaShare(key="green", layers=(PARKS,), radius_m=25)
NATURE = AreaShare(key="nature", layers=(NATURAL_LAND,), radius_m=25)
WATER = Proximity(key="water", layers=(WATER_AREAS, WATER_LINES), radius_m=50, sample_m=10)

# From engineered for wheels (1) to natural ground.
PREPARED = SurfaceScore(
    key="prepared",
    layers=(),
    surfaces={
        surface: score
        for score, surfaces in (
            (1.0, ("asphalt", "concrete", "concrete:plates", "paved", "chipseal")),
            (0.8, ("paving_stones", "concrete:lanes", "wood", "metal")),
            (0.6, ("sett", "cobblestone", "unhewn_cobblestone")),
            (0.5, ("compacted", "fine_gravel")),
            (0.4, ("gravel", "pebblestone", "unpaved")),
            (0.2, ("ground", "dirt", "earth", "woodchips")),
            (0.1, ("grass", "sand", "mud", "rock")),
        )
        for surface in surfaces
    },
    # Many footways and paths carry no surface, so it is guessed like other routers do.
    highways={
        highway: score
        for score, highways in (
            (
                1.0,
                (
                    "primary",
                    "primary_link",
                    "secondary",
                    "secondary_link",
                    "tertiary",
                    "tertiary_link",
                    "unclassified",
                    "residential",
                    "living_street",
                    "service",
                    "cycleway",
                ),
            ),
            (0.8, ("footway", "pedestrian", "steps")),
            (0.3, ("path", "bridleway")),
        )
        for highway in highways
    },
    tracktypes={"grade1": 1.0, "grade2": 0.5, "grade3": 0.4, "grade4": 0.2, "grade5": 0.1},
    track_default=0.4,
)

LAYERS: tuple[FeatureLayer, ...] = (PARKS, NATURAL_LAND, WATER_AREAS, WATER_LINES)
ATTRIBUTES: tuple[Attribute, ...] = (GREEN, NATURE, WATER, PREPARED)
