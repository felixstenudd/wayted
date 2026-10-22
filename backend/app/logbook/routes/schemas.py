from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, BaseModel, Field, StringConstraints, model_validator

from app.logbook.route_reviews.schemas import RouteReviewOut
from app.logbook.text import NO_NUL
from app.routing.attributes import KEYS
from app.routing.schemas import AttributeScoreOut, EdgeStepIn, WaypointIn

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


class RouteIn(BaseModel):
    name: Name
    activity: Activity
    shape: Shape
    # None for the most pleasant way to a finish, however long; a loop needs one.
    target_distance_m: int | None = Field(default=None, ge=1_000, le=200_000)
    preferences: Annotated[dict[str, Weight], AfterValidator(_known_keys)] = {}
    # the through points it was planned through, for planning it again
    waypoints: list[WaypointIn] = []
    edges: list[EdgeStepIn] = Field(min_length=1)

    @model_validator(mode="after")
    def _loop_has_target(self) -> Self:
        if self.shape == "loop" and self.target_distance_m is None:
            raise ValueError("a loop needs a target distance")
        return self


class RenameIn(BaseModel):
    name: Name


class RouteEdgeOut(BaseModel):
    seq: int
    length_m: float
    # index in the route's coordinates where this edge ends; it starts where the one before ends
    last_point: int


type Maneuver = Literal[
    "slight_left",
    "left",
    "sharp_left",
    "slight_right",
    "right",
    "sharp_right",
    "u_turn",
    "roundabout",
]


class RouteInstructionOut(BaseModel):
    seq: int
    # along the route from its start
    distance_m: float
    maneuver: Maneuver
    # roundabouts only: which exit to take, counting the one taken
    exit: int | None
    # the road turned onto, as its name or ref tag
    name: str | None
    # its highway tag, for a label when it has no name
    way_class: str | None


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
    target_distance_m: int | None
    preferences: dict[str, float]
    waypoints: list[WaypointIn]
    distance_m: float
    scores: dict[str, AttributeScoreOut]
    # metres climbed and dropped in all, as when saved; None when heights were not known
    ascent_m: float | None
    descent_m: float | None
    geometry: LineString
    edges: list[RouteEdgeOut]
    # turn by turn, in route order; none at the start and the finish
    instructions: list[RouteInstructionOut]
    review: RouteReviewOut | None
    created_at: datetime
    updated_at: datetime
