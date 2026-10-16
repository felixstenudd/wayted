from datetime import datetime

from pydantic import BaseModel, Field


class RouteReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


class RouteReviewUpdateIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


class RouteReviewOut(BaseModel):
    user_id: int
    route_id: int
    rating: int
    comment: str | None
    created_at: datetime
    updated_at: datetime


class RouteReviewSummaryOut(BaseModel):
    average_rating: float | None
    review_count: int


class SegmentRatingIn(BaseModel):
    segment_id: int
    rating: int = Field(ge=1, le=5)


class SegmentRatingOut(BaseModel):
    user_id: int
    segment_id: int
    rating: int
    created_at: datetime
    updated_at: datetime


class SegmentRatingSummaryOut(BaseModel):
    average_rating: float | None
    rating_count: int
