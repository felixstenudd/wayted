from typing import Annotated, Literal, Self

from pydantic import AfterValidator, BaseModel, Field, model_validator

from app.geojson import Feature, LineString

from .attributes import KEYS, Group
from .service import Reason, RouteWarning


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


class RouteRequestIn(BaseModel):
    activity: Literal["running", "cycling"]
    shape: Literal["loop", "point_to_point"]
    start: PointIn
    finish: PointIn | None = None
    target_distance_m: int = Field(ge=1_000, le=200_000)
    # -1 avoids, 0 does not mind, 1 prefers.
    preferences: Annotated[dict[str, Weight], AfterValidator(_known_keys)] = {}

    @model_validator(mode="after")
    def _finish_matches_shape(self) -> Self:
        if self.shape == "loop" and self.finish is not None:
            raise ValueError("a loop finishes at its start, so it takes no finish")
        if self.shape == "point_to_point" and self.finish is None:
            raise ValueError("a point to point route needs a finish")
        return self


class RoutePropertiesOut(BaseModel):
    length_m: float
    # attribute key -> length-weighted share of the route, 0..1, for the attributes that are scored
    scores: dict[str, float]
    # length travelled more than once
    reused_m: float
    # too_short: the finish is farther than the target; target_missed: no route came close
    warnings: list[RouteWarning]


class RouteOut(Feature[LineString, RoutePropertiesOut]):
    """The route as a GeoJSON Feature, its line in travel order."""


class PreparingOut(BaseModel):
    """The map data around the route is still being downloaded or scored; ask again shortly."""

    status: Literal["preparing"] = "preparing"


class NoRouteOut(BaseModel):
    """Why no route was found."""

    detail: Reason
