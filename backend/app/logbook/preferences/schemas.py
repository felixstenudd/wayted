from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from app.routing.attributes import KEYS

Weight = Annotated[float, Field(ge=-1, le=1)]


def _known_keys(weights: dict[str, float]) -> dict[str, float]:
    unknown = weights.keys() - KEYS
    if unknown:
        raise ValueError(f"unknown attributes: {', '.join(sorted(unknown))}")
    return weights


class PreferencesIn(BaseModel):
    # 0 ("don't mind") is the same as leaving the attribute out
    weights: Annotated[dict[str, Weight], AfterValidator(_known_keys)]


class PreferencesOut(BaseModel):
    weights: dict[str, float]
