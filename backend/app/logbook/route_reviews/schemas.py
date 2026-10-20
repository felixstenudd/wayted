from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, StringConstraints

from app.routing.attributes import ROUTE_ATTRIBUTES

SCORED = frozenset(a.key for a in ROUTE_ATTRIBUTES if a.scored)

# -1 wanted less, 0 about right, 1 wanted more
type Answer = Literal[-1, 0, 1]

Comment = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


def _scored_keys(answers: dict[str, int]) -> dict[str, int]:
    if not answers:
        raise ValueError("answer at least one attribute")
    unscored = answers.keys() - SCORED
    if unscored:
        raise ValueError(f"not scored attributes: {', '.join(sorted(unscored))}")
    return answers


class RouteReviewIn(BaseModel):
    answers: Annotated[dict[str, Answer], AfterValidator(_scored_keys)]
    comment: Comment | None = None


class RouteReviewOut(BaseModel):
    answers: dict[str, Answer]
    comment: str | None
    created_at: datetime
    updated_at: datetime


class PreferenceChangeOut(BaseModel):
    attribute: str
    before: float
    after: float


class SavedRouteReviewOut(BaseModel):
    review: RouteReviewOut
    # one per attribute whose answer changed, even when the weight was already at the end
    preference_changes: list[PreferenceChangeOut]
