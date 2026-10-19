"""Request and response bodies of the dev API. Everything drawn on the map is GeoJSON."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.sources.queue import Status
from app.sources.tiles import MAX_LATITUDE

MAX_RADIUS_M = 40_000

type Position = tuple[float, float]


class Point(BaseModel):
    type: Literal["Point"]
    coordinates: Position


class LineString(BaseModel):
    type: Literal["LineString"]
    coordinates: list[Position]


class Polygon(BaseModel):
    type: Literal["Polygon"]
    coordinates: list[list[Position]]


class MultiPolygon(BaseModel):
    type: Literal["MultiPolygon"]
    coordinates: list[list[list[Position]]]


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


class EdgeOut(BaseModel):
    id: int
    way_id: int
    source: int
    target: int
    length_m: float
    forward: list[str]
    backward: list[str]
    scores: dict[str, Any]
    tags: dict[str, str]


class VertexOut(BaseModel):
    id: int


class GraphOut(BaseModel):
    edges: FeatureCollection[LineString, EdgeOut]
    vertices: FeatureCollection[Point, VertexOut]


class AreaOut(BaseModel):
    layer: str
    osm_type: Literal["way", "relation"]
    osm_id: int
    tags: dict[str, str]


class MapperPendingOut(BaseModel):
    ways: int
    nodes: int


class EnricherPendingOut(BaseModel):
    ways: int
    relations: int
    nodes: int
    edges: int


class PendingOut(BaseModel):
    mapper: MapperPendingOut
    enricher: EnricherPendingOut


class BoundsOut(BaseModel):
    west: float
    south: float
    east: float
    north: float


class AreaRequestIn(BaseModel):
    lat: float = Field(ge=-MAX_LATITUDE, le=MAX_LATITUDE)
    lon: float = Field(ge=-180, le=180)
    radius_m: float = Field(gt=0, le=MAX_RADIUS_M)
    refetch: bool = False


class AreaRequestOut(BaseModel):
    queued: int
    queued_by_layer: dict[str, int]
    bounds: BoundsOut


class ErrorOut(BaseModel):
    detail: str
