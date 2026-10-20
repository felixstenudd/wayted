from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.logbook.routes.schemas import Activity, LineString

Comment = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
Reasons = Annotated[list[str], Field(min_length=1)]


class ReasonOut(BaseModel):
    code: str
    # per topic only a user's latest review counts
    topic: str
    sentiment: Literal[-1, 1]
    attribute: str | None


class SegmentReviewIn(BaseModel):
    # the stretch, as seq of the route's edges, both included
    from_seq: int = Field(ge=0)
    to_seq: int = Field(ge=0)
    reasons: Reasons
    comment: Comment | None = None

    @model_validator(mode="after")
    def _in_route_order(self) -> Self:
        if self.to_seq < self.from_seq:
            raise ValueError("to_seq comes before from_seq")
        return self


class SegmentReviewChangeIn(BaseModel):
    """Replaces the reasons and the comment; the stretch stays."""

    reasons: Reasons
    comment: Comment | None = None


class SegmentReviewOut(BaseModel):
    id: int
    # None once the route is deleted; the review still counts
    route_id: int | None
    from_seq: int | None
    to_seq: int | None
    activity: Activity
    geometry: LineString
    reasons: list[str]
    comment: str | None
    created_at: datetime
    updated_at: datetime
