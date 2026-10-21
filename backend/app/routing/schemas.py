from typing import Annotated, Literal, Self

from pydantic import AfterValidator, BaseModel, Field, model_validator

from app.geojson import Feature, LineString, Point

from .attributes import KEYS, Group
from .service import Reason, RerouteReason, RouteWarning


class AttributeOut(BaseModel):
    key: str
    group: Group
    scored: bool


class PointIn(BaseModel):
    lon: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)


def _known_keys(preferences: dict[str, float]) -> dict[str, float]:
    unknown = preferences.keys() - KEYS
    if unknown:
        raise ValueError(f"unknown attributes: {', '.join(sorted(unknown))}")
    return preferences


Weight = Annotated[float, Field(ge=-1, le=1)]


class WaypointIn(PointIn):
    # any: wherever it suits the route; asap: as soon as possible; after: after about after_m.
    at: Literal["any", "asap", "after"] = "any"
    after_m: int | None = Field(default=None, gt=0, le=200_000)

    @model_validator(mode="after")
    def _after_m_matches_at(self) -> Self:
        if (self.at == "after") != (self.after_m is not None):
            raise ValueError("after_m is needed for, and only for, at after")
        return self


class RouteRequestIn(BaseModel):
    activity: Literal["running", "cycling"]
    shape: Literal["loop", "point_to_point"]
    start: PointIn
    finish: PointIn | None = None
    # None for the most pleasant way to the finish, however long; a loop needs one.
    target_distance_m: int | None = Field(default=None, ge=1_000, le=200_000)
    # -1 avoids, 0 does not mind, 1 prefers.
    preferences: Annotated[dict[str, Weight], AfterValidator(_known_keys)] = {}
    # passed in the order the planner finds best, unless their at says otherwise
    waypoints: list[WaypointIn] = []

    @model_validator(mode="after")
    def _finish_matches_shape(self) -> Self:
        if self.shape == "loop" and self.finish is not None:
            raise ValueError("a loop finishes at its start, so it takes no finish")
        if self.shape == "point_to_point" and self.finish is None:
            raise ValueError("a point to point route needs a finish")
        if self.shape == "loop" and self.target_distance_m is None:
            raise ValueError("a loop needs a target distance")
        return self


class AttributeScoreOut(BaseModel):
    mean: float
    # share of the route's length that has a score for the attribute
    coverage: float


class EdgeStepIn(BaseModel):
    # within bigint, the graph's id type
    edge_id: int = Field(ge=-(2**63), le=2**63 - 1)
    # whether the route runs from the edge's source to its target
    forward: bool


class EdgeStepOut(BaseModel):
    edge_id: int
    # whether the route runs from the edge's source to its target
    forward: bool


class RoutePropertiesOut(BaseModel):
    length_m: float
    # for the attributes that are scored
    scores: dict[str, AttributeScoreOut]
    # length travelled more than once
    reused_m: float
    # too_short: the finish is farther than the target; target_missed: no route came close.
    # Always empty without a target.
    warnings: list[RouteWarning]
    # in travel order, as saving the route takes them
    edges: list[EdgeStepOut]
    # indexes into the request's waypoints, in the order the route passes them; empty for an
    # edited route, which passes them as it was planned to
    waypoint_order: list[int]


class PlannedRouteOut(Feature[LineString, RoutePropertiesOut]):
    """The route as a GeoJSON Feature, its line in travel order."""


class PlannedRoutesOut(BaseModel):
    """One to three routes that go different ways, the best first, as a GeoJSON
    FeatureCollection."""

    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[PlannedRouteOut]


class PreparingOut(BaseModel):
    """The map data around the route is still being downloaded or scored; ask again shortly."""

    status: Literal["preparing"] = "preparing"


class RerouteIn(BaseModel):
    activity: Literal["running", "cycling"]
    # the route as it is, in travel order
    edges: list[EdgeStepIn] = Field(min_length=1)
    # where on the route it was grabbed
    grab: PointIn
    # where it was dropped; leave out to take an edit back out
    drop: PointIn | None = None
    # for the warnings; leave out for a route without a target
    target_distance_m: int | None = Field(default=None, ge=1_000, le=200_000)


class RerouteOut(BaseModel):
    route: PlannedRouteOut
    # where the drop came onto the road, for its handle; null without a drop
    handle: Point | None


class NoRerouteOut(BaseModel):
    """Why the edit found no way."""

    detail: RerouteReason


class NoRouteOut(BaseModel):
    """Why no route was found."""

    detail: Reason
