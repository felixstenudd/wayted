"""The attributes a user can weight when asking for a route, in the order they are shown."""

from dataclasses import dataclass
from typing import Literal

from app.enrichment.definitions import ATTRIBUTES as SCORED

type Group = Literal["surroundings", "streets", "sights", "surface"]

_SCORED_KEYS = frozenset(a.key for a in SCORED)


@dataclass(frozen=True, slots=True)
class RouteAttribute:
    key: str
    group: Group

    @property
    def scored(self) -> bool:
        return self.key in _SCORED_KEYS


# Some are not scored yet; they are listed so the planner can show what is coming.
ROUTE_ATTRIBUTES: tuple[RouteAttribute, ...] = (
    RouteAttribute("green", "surroundings"),
    RouteAttribute("nature", "surroundings"),
    RouteAttribute("water", "surroundings"),
    RouteAttribute("quiet_streets", "streets"),
    RouteAttribute("sights", "sights"),
    RouteAttribute("bridges", "sights"),
    RouteAttribute("asphalt", "surface"),
    RouteAttribute("gravel", "surface"),
)

KEYS = frozenset(a.key for a in ROUTE_ATTRIBUTES)
