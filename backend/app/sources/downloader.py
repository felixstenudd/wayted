"""Downloader protocol"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from psycopg import AsyncConnection
from psycopg.rows import TupleRow

from .tiles import Bounds, TileRect


class DownloadStatus(StrEnum):
    OK = "ok"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    SOURCE_ERROR = "source_error"
    INVALID_RESPONSE = "invalid_response"
    STORAGE_ERROR = "storage_error"


class DownloadError(Exception):
    """Raised by a downloader when a fetch fails in a way it can classify."""

    def __init__(self, status: DownloadStatus, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass(frozen=True, slots=True)
class RectangleResult:
    rect: TileRect
    status: DownloadStatus
    message: str | None  # None when OK


class Downloader[P](Protocol):
    """
    A source for one or more layers fetched in the same request. Each layer is still its own
    download: its tiles are marked separately in raw.fetched_tiles.

    fetch never touches the database and store never touches the network, so no connection is
    held while waiting on the source.
    """

    layers: tuple[str, ...]  # ref.source_layers codes, all at the same zoom
    max_tiles: int
    max_extra_tiles: int
    max_requests: int  # rectangles fetched at once, as many as the source allows us

    async def fetch(self, bounds: Bounds) -> P: ...

    async def store(self, conn: AsyncConnection[TupleRow], payload: P) -> None: ...
