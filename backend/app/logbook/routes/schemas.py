from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class RouteType(str, Enum):
    loop = "loop"
    out_and_back = "out_and_back"
    point_to_point = "point_to_point"


class RouteCreateIn(BaseModel):
    name: str | None = None
    activity_id: int
    route_type: RouteType
    distance_m: float = Field(ge=0)
    geom: str = Field(description="Route geometry as WKT.")
    is_public: bool = False


class RouteUpdateIn(BaseModel):
    name: str | None = None
    activity_id: int
    route_type: RouteType
    distance_m: float = Field(ge=0)
    geom: str
    is_public: bool


class RouteOut(BaseModel):
    id: int
    user_id: int
    name: str | None
    activity_id: int
    route_type: RouteType
    distance_m: float
    geom: str
    is_public: bool
    created_at: datetime
    updated_at: datetime


class RouteSaveIn(BaseModel):
    route_id: int


class RouteSaveOut(BaseModel):
    user_id: int
    route_id: int
    created_at: datetime


class SavedRouteOut(BaseModel):
    id: int
    name: str | None
    activity_id: int
    route_type: RouteType
    distance_m: float
    geom: str
    is_public: bool
    created_at: datetime
    saved_at: datetime


class RouteSaveStatusOut(BaseModel):
    is_saved: bool


class RouteSaveCountOut(BaseModel):
    save_count: int
