from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, StringConstraints

from app.logbook.route_reviews.schemas import RouteReviewOut
from app.logbook.text import NO_NUL
from app.routing.attributes import KEYS

type Activity = Literal["running", "cycling"]
type Shape = Literal["loop", "point_to_point"]
type Position = tuple[float, float]

Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80, pattern=NO_NUL)
]
Weight = Annotated[float, Field(ge=-1, le=1)]


def _known_keys(preferences: dict[str, float]) -> dict[str, float]:
    unknown = preferences.keys() - KEYS
    if unknown:
        raise ValueError(f"unknown attributes: {', '.join(sorted(unknown))}")
    return preferences


class LineString(BaseModel):
    type: Literal["LineString"]
    coordinates: list[Position]


class EdgeStepIn(BaseModel):
    # within bigint, the graph's id type
    edge_id: int = Field(ge=-(2**63), le=2**63 - 1)
    # whether the route runs from the edge's source to its target
    forward: bool


class RouteIn(BaseModel):
    name: Name
    activity: Activity
    shape: Shape
    target_distance_m: int = Field(ge=1_000, le=200_000)
    preferences: Annotated[dict[str, Weight], AfterValidator(_known_keys)] = {}
    edges: list[EdgeStepIn] = Field(min_length=1)


class RenameIn(BaseModel):
    name: Name


class AttributeScoreOut(BaseModel):
    mean: float
    # share of the route's length that has a score for the attribute
    coverage: float


class RouteEdgeOut(BaseModel):
    seq: int
    length_m: float
    # index in the route's coordinates where this edge ends; it starts where the one before ends
    last_point: int


class RouteSummaryOut(BaseModel):
    id: int
    name: str
    activity: Activity
    shape: Shape
    distance_m: float
    created_at: datetime
    # simplified, for drawing many routes at once
    geometry: LineString


class RouteOut(BaseModel):
    id: int
    name: str
    activity: Activity
    shape: Shape
    target_distance_m: int
    preferences: dict[str, float]
    distance_m: float
    scores: dict[str, AttributeScoreOut]
    geometry: LineString
    edges: list[RouteEdgeOut]
    review: RouteReviewOut | None
    created_at: datetime
    updated_at: datetime
