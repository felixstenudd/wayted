"""GeoJSON geometries and features, for everything the APIs draw on a map."""

from typing import Literal

from pydantic import BaseModel

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
