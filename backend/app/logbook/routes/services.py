from uuid import UUID

from psycopg import AsyncConnection
from shapely import wkt
from shapely.errors import GEOSException
from shapely.geometry import LineString

from app.logbook.routes.queries import (
    CREATE_ROUTE,
    GET_ACCESSIBLE_ROUTE_BY_ID,
    LIST_USER_ROUTES,
    LIST_PUBLIC_ROUTES,
    LIST_PUBLIC_ROUTES_BY_ACTIVITY,
    SEARCH_PUBLIC_ROUTES_NEAR_POINT,
    UPDATE_ROUTE,
    UPDATE_ROUTE_GEOMETRY,
    DELETE_ROUTE,
    SAVE_ROUTE,
    UNSAVE_ROUTE,
    LIST_SAVED_ROUTES,
    IS_ROUTE_SAVED,
    COUNT_ROUTE_SAVES,
)


class RouteError(Exception):
    """Base exception for route services."""


class RouteInvalidInput(RouteError):
    pass


class RouteNotFound(RouteError):
    pass


def validate_route_geometry(geom_wkt: str) -> str:
    """Validate WKT LineString geometry using longitude/latitude coordinates."""
    if not geom_wkt or not geom_wkt.strip():
        raise RouteInvalidInput("Route geometry cannot be empty.")

    try:
        geom = wkt.loads(geom_wkt)
    except (GEOSException, ValueError, TypeError) as exc:
        raise RouteInvalidInput("Invalid WKT geometry.") from exc

    if not isinstance(geom, LineString):
        raise RouteInvalidInput("Route geometry must be a LineString.")

    if geom.is_empty or not geom.is_valid:
        raise RouteInvalidInput("Route geometry is empty or invalid.")

    if len(geom.coords) < 2:
        raise RouteInvalidInput("A route must contain at least two points.")

    for lon, lat, *_ in geom.coords:
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise RouteInvalidInput(
                "Coordinates must use longitude and latitude in SRID 4326."
            )

    return geom.wkt


async def create_route(
    user_id: UUID,
    name: str | None,
    activity_id: int,
    route_type: str,
    distance_m: float,
    geom_wkt: str,
    is_public: bool,
    db_conn: AsyncConnection,
):
    if distance_m < 0:
        raise RouteInvalidInput("Distance cannot be negative.")

    geom_wkt = validate_route_geometry(geom_wkt)

    cur = await db_conn.execute(
        CREATE_ROUTE,
        (
            user_id,
            name,
            activity_id,
            route_type,
            distance_m,
            geom_wkt,
            is_public,
        ),
    )
    return await cur.fetchone()


async def get_route(
    route_id: int,
    user_id: UUID,
    db_conn: AsyncConnection,
):
    cur = await db_conn.execute(
        GET_ACCESSIBLE_ROUTE_BY_ID,
        (route_id, user_id),
    )
    route = await cur.fetchone()

    if route is None:
        raise RouteNotFound("Route not found.")

    return route


async def list_user_routes(
    user_id: UUID,
    limit: int,
    offset: int,
    db_conn: AsyncConnection,
):
    _validate_pagination(limit, offset)

    cur = await db_conn.execute(
        LIST_USER_ROUTES,
        (user_id, limit, offset),
    )
    return await cur.fetchall()


async def list_public_routes(
    limit: int,
    offset: int,
    db_conn: AsyncConnection,
):
    _validate_pagination(limit, offset)

    cur = await db_conn.execute(
        LIST_PUBLIC_ROUTES,
        (limit, offset),
    )
    return await cur.fetchall()


async def list_public_routes_by_activity(
    activity_id: int,
    limit: int,
    offset: int,
    db_conn: AsyncConnection,
):
    _validate_pagination(limit, offset)

    cur = await db_conn.execute(
        LIST_PUBLIC_ROUTES_BY_ACTIVITY,
        (activity_id, limit, offset),
    )
    return await cur.fetchall()


async def search_public_routes_near_point(
    longitude: float,
    latitude: float,
    radius_m: float,
    limit: int,
    offset: int,
    db_conn: AsyncConnection,
):
    if not -180 <= longitude <= 180:
        raise RouteInvalidInput("Longitude must be between -180 and 180.")

    if not -90 <= latitude <= 90:
        raise RouteInvalidInput("Latitude must be between -90 and 90.")

    if radius_m <= 0:
        raise RouteInvalidInput("Search radius must be positive.")

    _validate_pagination(limit, offset)

    cur = await db_conn.execute(
        SEARCH_PUBLIC_ROUTES_NEAR_POINT,
        (longitude, latitude, radius_m, limit, offset),
    )
    return await cur.fetchall()


async def update_route(
    route_id: int,
    user_id: UUID,
    name: str | None,
    activity_id: int,
    route_type: str,
    distance_m: float,
    is_public: bool,
    db_conn: AsyncConnection,
):
    if distance_m < 0:
        raise RouteInvalidInput("Distance cannot be negative.")

    cur = await db_conn.execute(
        UPDATE_ROUTE,
        (
            name,
            activity_id,
            route_type,
            distance_m,
            is_public,
            route_id,
            user_id,
        ),
    )
    route = await cur.fetchone()

    if route is None:
        raise RouteNotFound("Route not found or you do not own it.")

    return route


async def update_route_geometry(
    route_id: int,
    user_id: UUID,
    geom_wkt: str,
    distance_m: float,
    db_conn: AsyncConnection,
):
    if distance_m < 0:
        raise RouteInvalidInput("Distance cannot be negative.")

    geom_wkt = validate_route_geometry(geom_wkt)

    cur = await db_conn.execute(
        UPDATE_ROUTE_GEOMETRY,
        (geom_wkt, distance_m, route_id, user_id),
    )
    route = await cur.fetchone()

    if route is None:
        raise RouteNotFound("Route not found or you do not own it.")

    return route


async def delete_route(
    route_id: int,
    user_id: UUID,
    db_conn: AsyncConnection,
):
    cur = await db_conn.execute(
        DELETE_ROUTE,
        (route_id, user_id),
    )
    row = await cur.fetchone()

    if row is None:
        raise RouteNotFound("Route not found or you do not own it.")

    return row


async def save_route(
    user_id: UUID,
    route_id: int,
    db_conn: AsyncConnection,
):
    cur = await db_conn.execute(
        SAVE_ROUTE,
        (user_id, route_id, user_id),
    )
    row = await cur.fetchone()

    if row is not None:
        return row

    # A missing RETURNING row can mean either a duplicate save
    # or a route that is unavailable to this user.
    cur = await db_conn.execute(
        GET_ACCESSIBLE_ROUTE_BY_ID,
        (route_id, user_id),
    )
    if await cur.fetchone() is None:
        raise RouteNotFound("Route not found or unavailable.")

    return None


async def unsave_route(
    user_id: UUID,
    route_id: int,
    db_conn: AsyncConnection,
):
    cur = await db_conn.execute(
        UNSAVE_ROUTE,
        (user_id, route_id),
    )
    return await cur.fetchone()


async def list_saved_routes(
    user_id: UUID,
    limit: int,
    offset: int,
    db_conn: AsyncConnection,
):
    _validate_pagination(limit, offset)

    cur = await db_conn.execute(
        LIST_SAVED_ROUTES,
        (user_id, limit, offset),
    )
    return await cur.fetchall()


async def is_route_saved(
    user_id: UUID,
    route_id: int,
    db_conn: AsyncConnection,
) -> bool:
    cur = await db_conn.execute(
        IS_ROUTE_SAVED,
        (user_id, route_id),
    )
    row = await cur.fetchone()
    return row[0]


async def count_route_saves(
    route_id: int,
    db_conn: AsyncConnection,
) -> int:
    cur = await db_conn.execute(
        COUNT_ROUTE_SAVES,
        (route_id,),
    )
    row = await cur.fetchone()
    return row[0]


def _validate_pagination(limit: int, offset: int) -> None:
    if not 1 <= limit <= 100:
        raise RouteInvalidInput("Limit must be between 1 and 100.")

    if offset < 0:
        raise RouteInvalidInput("Offset cannot be negative.")
