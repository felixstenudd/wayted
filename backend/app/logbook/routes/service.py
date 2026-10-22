from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from . import queries
from .export import FIT_MEDIA_TYPE, GPX_MEDIA_TYPE, ExportFile, slug
from .fit import Course, CoursePoint, CourseTurn, encode_course
from .schemas import RouteIn, RouteOut, RouteSummaryOut


class RouteError(Exception):
    """Base for errors the router turns into HTTP responses."""


class InvalidRoute(RouteError):
    pass


class RouteNotFound(RouteError):
    pass


async def create_route(user_id: UUID, route: RouteIn, conn: AsyncConnection[Any]) -> RouteOut:
    """Save a route from its edges; its line, distance and scores come from the graph."""
    steps = {
        "edge_ids": [e.edge_id for e in route.edges],
        "forward": [e.forward for e in route.edges],
    }
    await _check_steps(conn, steps, route.activity)
    cur = await conn.execute(
        queries.CREATE_ROUTE,
        steps
        | {
            "user_id": user_id,
            "name": route.name,
            "activity": route.activity,
            "shape": route.shape,
            "target_distance_m": route.target_distance_m,
            "preferences": Jsonb(route.preferences),
            "waypoints": Jsonb([w.model_dump() for w in route.waypoints]),
        },
    )
    row = await cur.fetchone()
    assert row is not None
    return await get_route(user_id, row[0], conn)


async def _check_steps(conn: AsyncConnection[Any], steps: dict[str, Any], activity: str) -> None:
    cur = await conn.execute(queries.STEPS, steps | {"activity": activity})
    previous_end = None
    for seq, edge_id, start, end, allowed in await cur.fetchall():
        if start is None:
            raise InvalidRoute(f"Edge {edge_id} is not in the map.")
        if seq > 0 and start != previous_end:
            raise InvalidRoute(f"Edge {edge_id} does not continue from the edge before it.")
        if not allowed:
            raise InvalidRoute(f"Edge {edge_id} cannot be used for {activity} in this direction.")
        previous_end = end


async def get_route(user_id: UUID, route_id: int, conn: AsyncConnection[Any]) -> RouteOut:
    cur = conn.cursor(row_factory=dict_row)
    await cur.execute(queries.GET_ROUTE, {"user_id": user_id, "route_id": route_id})
    row = await cur.fetchone()
    if row is None:
        raise RouteNotFound("Route not found.")
    return RouteOut.model_validate(row)


async def list_routes(user_id: UUID, conn: AsyncConnection[Any]) -> list[RouteSummaryOut]:
    cur = conn.cursor(row_factory=dict_row)
    await cur.execute(queries.LIST_ROUTES, {"user_id": user_id})
    return [RouteSummaryOut.model_validate(row) for row in await cur.fetchall()]


async def rename_route(
    user_id: UUID, route_id: int, name: str, conn: AsyncConnection[Any]
) -> RouteSummaryOut:
    cur = conn.cursor(row_factory=dict_row)
    await cur.execute(
        queries.RENAME_ROUTE, {"user_id": user_id, "route_id": route_id, "name": name}
    )
    row = await cur.fetchone()
    if row is None:
        raise RouteNotFound("Route not found.")
    return RouteSummaryOut.model_validate(row)


async def delete_route(user_id: UUID, route_id: int, conn: AsyncConnection[Any]) -> None:
    cur = await conn.execute(queries.DELETE_ROUTE, {"user_id": user_id, "route_id": route_id})
    if await cur.fetchone() is None:
        raise RouteNotFound("Route not found.")


async def export_gpx(user_id: UUID, route_id: int, conn: AsyncConnection[Any]) -> ExportFile:
    """The route as a GPX 1.1 track with a waypoint per turn. Raises RouteNotFound unless it is
    one of the user's.
    """
    cur = await conn.execute(queries.EXPORT_GPX, {"user_id": user_id, "route_id": route_id})
    row = await cur.fetchone()
    if row is None:
        raise RouteNotFound("Route not found.")
    name, gpx = row
    return ExportFile(f"{slug(name, route_id)}.gpx", GPX_MEDIA_TYPE, gpx)


async def export_fit(user_id: UUID, route_id: int, conn: AsyncConnection[Any]) -> ExportFile:
    """The route as a FIT course with a course point per turn. Raises RouteNotFound unless it is
    one of the user's.
    """
    cur = await conn.execute(queries.EXPORT_FIT, {"user_id": user_id, "route_id": route_id})
    row = await cur.fetchone()
    if row is None:
        raise RouteNotFound("Route not found.")
    name, activity, lons, lats, distances, elevations, points, maneuvers, angles, labels = row
    course = Course(
        route_id=route_id,
        name=name,
        activity=activity,
        points=[
            CoursePoint(lon, lat, distance_m, altitude_m)
            for lon, lat, distance_m, altitude_m in zip(
                lons, lats, distances, elevations or [None] * len(lons), strict=True
            )
        ],
        turns=[CourseTurn(*turn) for turn in zip(points, maneuvers, angles, labels, strict=True)],
    )
    return ExportFile(
        f"{slug(name, route_id)}.fit", FIT_MEDIA_TYPE, encode_course(course, datetime.now(UTC))
    )
