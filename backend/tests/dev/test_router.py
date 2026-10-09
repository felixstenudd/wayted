import httpx
import pytest
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

from app.sources import queue
from app.sources.registry import mark_fetched
from app.sources.tiles import Tile

pytestmark = pytest.mark.db

type Conn = AsyncConnection[TupleRow]
type Pool = AsyncConnectionPool[Conn]

TILE = Tile(x=8800, y=4700, z=14)


async def test_health(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")

    assert (response.status_code, response.json()) == (200, {"status": "ok"})


async def test_fetched_tiles_are_polygons_with_their_times(
    client: httpx.AsyncClient, downloader_pool: Pool
) -> None:
    async with downloader_pool.connection() as conn:
        await mark_fetched(conn, "roads", {TILE})

    response = await client.get("/tiles/fetched")

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "FeatureCollection"
    [feature] = body["features"]
    assert feature["type"] == "Feature"
    b = TILE.bounds
    assert feature["geometry"] == {
        "type": "Polygon",
        "coordinates": [
            [
                [b.west, b.south],
                [b.east, b.south],
                [b.east, b.north],
                [b.west, b.north],
                [b.west, b.south],
            ]
        ],
    }
    properties = feature["properties"]
    assert (properties["layer"], properties["z"], properties["x"], properties["y"]) == (
        "roads",
        14,
        8800,
        4700,
    )
    assert properties["fetched_at"] < properties["expires_at"]


async def test_queued_tiles_show_why_one_failed(
    client: httpx.AsyncClient, admin_conn: Conn, api_pool: Pool
) -> None:
    async with api_pool.connection() as conn:
        await queue.request_area(conn, TILE.bounds)
    await admin_conn.execute(
        """
        UPDATE raw.pending_tiles
        SET status = 'failed', attempts = 10, last_status = 'timeout', last_message = 'too slow'
        WHERE layer = 'roads'
        """
    )

    response = await client.get("/tiles/queued")

    assert response.status_code == 200
    by_layer = {f["properties"]["layer"]: f for f in response.json()["features"]}
    assert set(by_layer) == {"roads", "parks"}
    assert by_layer["roads"]["geometry"]["type"] == "Polygon"
    failed = by_layer["roads"]["properties"]
    assert (
        failed["status"],
        failed["attempts"],
        failed["last_status"],
        failed["last_message"],
    ) == (
        "failed",
        10,
        "timeout",
        "too slow",
    )
    waiting = by_layer["parks"]["properties"]
    assert (waiting["status"], waiting["attempts"], waiting["last_status"]) == ("pending", 0, None)
    assert waiting["requested_at"] <= waiting["next_attempt_at"]
