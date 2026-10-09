"""Request and response bodies of the dev API. Everything drawn on the map is GeoJSON."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.sources.queue import Status

type Position = tuple[float, float]


class Polygon(BaseModel):
    type: Literal["Polygon"]
    coordinates: list[list[Position]]


class Feature[Geometry, Properties](BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: Geometry
    properties: Properties


class FeatureCollection[Geometry, Properties](BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[Feature[Geometry, Properties]]


class FetchedTileOut(BaseModel):
    layer: str
    z: int
    x: int
    y: int
    fetched_at: datetime
    expires_at: datetime


class QueuedTileOut(BaseModel):
    layer: str
    z: int
    x: int
    y: int
    requested_at: datetime
    status: Status
    attempts: int
    next_attempt_at: datetime
    last_status: str | None
    last_message: str | None
