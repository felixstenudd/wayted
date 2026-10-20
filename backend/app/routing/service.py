"""
Plans routes with routing.plan_route in the database. The map data around a route is downloaded
and scored first: prepare queues what is missing and says when everything is in the graph.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, cast, get_args

import psycopg
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg.types.json import Jsonb

from app.sources.queue import request_area, waiting_in_bounds
from app.sources.tiles import Bounds

from .attributes import ROUTE_ATTRIBUTES

type Activity = Literal["running", "cycling"]
# The detail of routing.plan_route's no_data_found errors.
type Reason = Literal["start_off_road", "finish_off_road", "unreachable", "no_loop"]
type RouteWarning = Literal["too_short", "target_missed"]

REASONS: frozenset[str] = frozenset(get_args(Reason.__value__))

# The longest a request may hold a connection; a route that takes longer is not worth waiting for.
PLAN_TIMEOUT = "30s"

# Weights for attributes the enricher does not score yet would only dilute the others.
SCORED_KEYS = frozenset(a.key for a in ROUTE_ATTRIBUTES if a.scored)

# ST_Point is strict, so a NULL finish stays NULL: a loop.
POINTS = """
    ST_Point(%(start_lon)s, %(start_lat)s, 4326), ST_Point(%(finish_lon)s, %(finish_lat)s, 4326)
"""

SEARCH_BOUNDS = f"""
    SELECT ST_XMin(area), ST_YMin(area), ST_XMax(area), ST_YMax(area)
    FROM routing.search_area({POINTS}, %(target_m)s) AS area
"""

# The enricher scores new and moved edges after the mapper builds them; until then they count as
# neither preferred nor avoided.
UNSCORED_IN_BOUNDS = """
    SELECT EXISTS (
        SELECT FROM graph.pending_edges queued JOIN graph.edges edge ON edge.id = queued.edge_id
        WHERE edge.geom && ST_MakeEnvelope(%(west)s, %(south)s, %(east)s, %(north)s, 4326)
    )
"""

SET_TIMEOUT = f"SET LOCAL statement_timeout = '{PLAN_TIMEOUT}'"

PLAN_ROUTE = f"""
    SELECT routing.plan_route(%(activity)s, {POINTS}, %(target_m)s, %(weights)s)
"""


class NoRoute(Exception):
    """The database found no route; reason says why."""

    def __init__(self, reason: Reason) -> None:
        super().__init__(reason)
        self.reason: Reason = reason


class PlanningTimeout(Exception):
    """Planning took longer than PLAN_TIMEOUT."""


@dataclass(frozen=True, slots=True)
class Coordinate:
    lon: float
    lat: float


@dataclass(frozen=True, slots=True)
class RouteQuery:
    activity: Activity
    start: Coordinate
    # None for a loop back to the start
    finish: Coordinate | None
    target_m: float
    # attribute key -> weight from -1 (avoid) to 1 (prefer)
    weights: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class PlannedRoute:
    # GeoJSON LineString in travel order
    geometry: dict[str, Any]
    length_m: float
    # score key -> length-weighted share along the route, 0..1
    scores: dict[str, float]
    # length travelled more than once
    reused_m: float
    warnings: list[RouteWarning]


def _params(query: RouteQuery) -> dict[str, Any]:
    return {
        "activity": query.activity,
        "start_lon": query.start.lon,
        "start_lat": query.start.lat,
        "finish_lon": query.finish.lon if query.finish else None,
        "finish_lat": query.finish.lat if query.finish else None,
        "target_m": query.target_m,
        "weights": Jsonb({k: w for k, w in query.weights.items() if k in SCORED_KEYS}),
    }


async def search_bounds(conn: AsyncConnection[TupleRow], query: RouteQuery) -> Bounds:
    """The bounds of the area routing.plan_route reads for query."""
    cur = await conn.execute(SEARCH_BOUNDS, _params(query))
    row = await cur.fetchone()
    assert row is not None
    west, south, east, north = row
    return Bounds(west=west, south=south, east=east, north=north)


async def prepare(conn: AsyncConnection[TupleRow], query: RouteQuery) -> bool:
    """
    Queue the tiles the route needs that are not fetched, and return whether its whole area is
    in the graph and scored. Runs in the caller's transaction; commit for the worker to see it.
    """
    bounds = await search_bounds(conn, query)
    await request_area(conn, bounds)
    if await waiting_in_bounds(conn, bounds):
        return False
    cur = await conn.execute(
        UNSCORED_IN_BOUNDS,
        {"west": bounds.west, "south": bounds.south, "east": bounds.east, "north": bounds.north},
    )
    row = await cur.fetchone()
    assert row is not None
    return not row[0]


async def plan(conn: AsyncConnection[TupleRow], query: RouteQuery) -> PlannedRoute:
    """
    Plan a route of about query.target_m. Weights for attributes that are not scored are dropped.

    Raises NoRoute when there is none, and PlanningTimeout when planning takes too long.
    """
    try:
        async with conn.transaction():
            await conn.execute(SET_TIMEOUT)
            cur = await conn.execute(PLAN_ROUTE, _params(query))
            row = await cur.fetchone()
    except psycopg.errors.NoDataFound as e:
        reason = e.diag.message_detail
        if reason not in REASONS:
            raise
        raise NoRoute(cast(Reason, reason)) from None
    except psycopg.errors.QueryCanceled:
        raise PlanningTimeout(f"Planning took longer than {PLAN_TIMEOUT}.") from None
    assert row is not None
    route: dict[str, Any] = row[0]
    return PlannedRoute(
        geometry=route["geometry"],
        length_m=route["length_m"],
        scores=route["scores"],
        reused_m=route["reused_m"],
        warnings=route["warnings"],
    )
