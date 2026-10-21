"""
Plans routes with routing.plan_route in the database. The map data around a route is downloaded
and scored first: prepare queues what is missing and says when everything is in the graph.
"""

from collections.abc import Mapping, Sequence
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
type Reason = Literal[
    "start_off_road", "waypoint_off_road", "finish_off_road", "unreachable", "no_loop"
]
# any: wherever it suits the route; asap: as soon as possible; after: after about after_m.
type WaypointAt = Literal["any", "asap", "after"]
type RouteWarning = Literal["too_short", "target_missed"]

REASONS: frozenset[str] = frozenset(get_args(Reason.__value__))
# The detail of routing.reroute's no_data_found errors.
type RerouteReason = Literal["drop_off_road", "unreachable"]
REROUTE_REASONS: frozenset[str] = frozenset(get_args(RerouteReason.__value__))

# The longest a request may hold a connection; a route that takes longer is not worth waiting for.
PLAN_TIMEOUT = "30s"

# Weights for attributes the enricher does not score yet would only dilute the others.
SCORED_KEYS = frozenset(a.key for a in ROUTE_ATTRIBUTES if a.scored)

# ST_Point is strict, so a NULL finish stays NULL: a loop.
POINTS = """
    ST_Point(%(start_lon)s, %(start_lat)s, 4326), ST_Point(%(finish_lon)s, %(finish_lat)s, 4326)
"""

# The waypoints in the order routing.plan_route passes them, which shapes the area.
SEARCH_BOUNDS = f"""
    WITH points (start, finish) AS (SELECT {POINTS})
    SELECT ST_XMin(area), ST_YMin(area), ST_XMax(area), ST_YMax(area)
    FROM points, routing.search_area(
        start,
        finish,
        %(target_m)s,
        routing.defaults() -> 'area',
        ARRAY(
            SELECT t.geom
            FROM routing.travel_points(start, coalesce(finish, start), %(waypoints)s) t
            WHERE t.n IS NOT NULL
            ORDER BY t.k
        )
    ) AS area
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

REROUTE = """
    SELECT routing.reroute(
        %(activity)s,
        %(edge_ids)s::bigint[],
        %(forward)s::boolean[],
        ST_Point(%(grab_lon)s, %(grab_lat)s, 4326),
        ST_Point(%(drop_lon)s, %(drop_lat)s, 4326),
        %(target_m)s,
        %(before_m)s,
        %(after_m)s
    )
"""

PLAN_ROUTE = f"""
    SELECT routing.plan_route(
        %(activity)s, {POINTS}, %(target_m)s, %(weights)s, '{{}}', %(waypoints)s
    )
"""


class NoRoute(Exception):
    """The database found no route; reason says why."""

    def __init__(self, reason: Reason) -> None:
        super().__init__(reason)
        self.reason: Reason = reason


class NoReroute(Exception):
    """The database found no way for an edit; reason says why."""

    def __init__(self, reason: RerouteReason) -> None:
        super().__init__(reason)
        self.reason: RerouteReason = reason


class InvalidEdges(Exception):
    """The edges to edit are not a route the activity can travel."""


class PlanningTimeout(Exception):
    """Planning took longer than PLAN_TIMEOUT."""


@dataclass(frozen=True, slots=True)
class Coordinate:
    lon: float
    lat: float


@dataclass(frozen=True, slots=True)
class Waypoint:
    point: Coordinate
    at: WaypointAt
    # only for at after
    after_m: float | None


@dataclass(frozen=True, slots=True)
class RouteQuery:
    activity: Activity
    start: Coordinate
    # None for a loop back to the start
    finish: Coordinate | None
    # None for the most pleasant way to the finish, however long; a loop needs one
    target_m: float | None
    # attribute key -> weight from -1 (avoid) to 1 (prefer)
    weights: Mapping[str, float]
    # points the route passes, in the order given
    waypoints: tuple[Waypoint, ...] = ()


@dataclass(frozen=True, slots=True)
class EdgeStep:
    edge_id: int
    # whether the route runs from the edge's source to its target
    forward: bool


@dataclass(frozen=True, slots=True)
class AttributeScore:
    # mean over the length that has a score for the attribute
    mean: float
    # share of the route's length that has one
    coverage: float


@dataclass(frozen=True, slots=True)
class PlannedRoute:
    # GeoJSON LineString in travel order
    geometry: dict[str, Any]
    length_m: float
    scores: dict[str, AttributeScore]
    # length travelled more than once
    reused_m: float
    warnings: list[RouteWarning]
    # in travel order
    edges: list[EdgeStep]
    # indexes into RouteQuery.waypoints, in the order the route passes them
    waypoint_order: list[int]


def _params(query: RouteQuery) -> dict[str, Any]:
    return {
        "activity": query.activity,
        "start_lon": query.start.lon,
        "start_lat": query.start.lat,
        "finish_lon": query.finish.lon if query.finish else None,
        "finish_lat": query.finish.lat if query.finish else None,
        "target_m": query.target_m,
        "weights": Jsonb({k: w for k, w in query.weights.items() if k in SCORED_KEYS}),
        "waypoints": Jsonb([_waypoint(w) for w in query.waypoints]),
    }


def _waypoint(waypoint: Waypoint) -> dict[str, Any]:
    out: dict[str, Any] = {"lon": waypoint.point.lon, "lat": waypoint.point.lat, "at": waypoint.at}
    if waypoint.after_m is not None:
        out["after_m"] = waypoint.after_m
    return out


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


async def plan(conn: AsyncConnection[TupleRow], query: RouteQuery) -> list[PlannedRoute]:
    """
    Plan a route of about query.target_m, or the most pleasant way to the finish without one,
    with up to two other options that go other ways: the best first. Weights for attributes that
    are not scored are dropped.

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
    return [_planned(route), *(_planned(option) for option in route["options"])]


def _planned(route: dict[str, Any]) -> PlannedRoute:
    return PlannedRoute(
        geometry=route["geometry"],
        length_m=route["length_m"],
        scores={key: AttributeScore(**score) for key, score in route["scores"].items()},
        reused_m=route["reused_m"],
        warnings=route["warnings"],
        edges=[EdgeStep(**step) for step in route["edges"]],
        waypoint_order=route["waypoint_order"],
    )


@dataclass(frozen=True, slots=True)
class Edit:
    activity: Activity
    # the route as it is, in travel order
    edges: Sequence[EdgeStep]
    # where on the route it was grabbed
    grab: Coordinate
    # where it was dropped; None takes an edit back out
    drop: Coordinate | None
    # for the warnings; None for a route without a target
    target_m: float | None
    # how far before and after the grab to reroute at least: an earlier edit's, to take it out
    before_m: float | None = None
    after_m: float | None = None


@dataclass(frozen=True, slots=True)
class Rerouted:
    route: PlannedRoute
    # where the drop came onto the road; None without a drop
    handle: Coordinate | None
    # how far the new stretch reaches before and after the handle; None without a drop
    before_m: float | None
    after_m: float | None


async def reroute(conn: AsyncConnection[TupleRow], edit: Edit) -> Rerouted:
    """
    The route with the stretch around edit.grab routed again through the road nearest edit.drop,
    where the drop came onto that road, and how far the stretch reached.

    Raises InvalidEdges for edges that are not a route, NoReroute when there is no way, and
    PlanningTimeout when it takes too long.
    """
    params = {
        "activity": edit.activity,
        "edge_ids": [e.edge_id for e in edit.edges],
        "forward": [e.forward for e in edit.edges],
        "grab_lon": edit.grab.lon,
        "grab_lat": edit.grab.lat,
        "drop_lon": edit.drop.lon if edit.drop else None,
        "drop_lat": edit.drop.lat if edit.drop else None,
        "target_m": edit.target_m,
        "before_m": edit.before_m,
        "after_m": edit.after_m,
    }
    try:
        async with conn.transaction():
            await conn.execute(SET_TIMEOUT)
            cur = await conn.execute(REROUTE, params)
            row = await cur.fetchone()
    except psycopg.errors.InvalidParameterValue as e:
        raise InvalidEdges(e.diag.message_primary or "") from None
    except psycopg.errors.NoDataFound as e:
        reason = e.diag.message_detail
        if reason not in REROUTE_REASONS:
            raise
        raise NoReroute(cast(RerouteReason, reason)) from None
    except psycopg.errors.QueryCanceled:
        raise PlanningTimeout(f"Editing took longer than {PLAN_TIMEOUT}.") from None
    assert row is not None
    route: dict[str, Any] = row[0]
    handle = route["handle"]
    return Rerouted(
        route=_planned(route | {"waypoint_order": []}),
        handle=Coordinate(*handle["coordinates"]) if handle else None,
        before_m=route["before_m"],
        after_m=route["after_m"],
    )
