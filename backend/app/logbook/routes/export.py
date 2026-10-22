"""Saved routes as files for other apps and devices."""

import re
import unicodedata
from dataclasses import dataclass

GPX_MEDIA_TYPE = "application/gpx+xml"
FIT_MEDIA_TYPE = "application/vnd.ant.fit"

_SLUG_MAX_CHARS = 60
_NOT_SLUG = re.compile(r"[^a-z0-9]+")
# Letters that NFD does not split into a base letter and a mark, which would otherwise be lost.
# Applied after lowercasing. The frontend's slug uses the same table.
_PLAIN_LETTERS = str.maketrans(
    {"ø": "o", "æ": "ae", "œ": "oe", "ß": "ss", "ł": "l", "đ": "d", "ð": "d", "þ": "th", "ı": "i"}
)


@dataclass(frozen=True, slots=True)
class ExportFile:
    filename: str
    media_type: str
    content: str | bytes


def slug(name: str, route_id: int) -> str:
    """The route name as a file name stem: plain lowercase letters and digits joined by dashes.

    `route-{id}` when nothing is left. Same rule as `slug` in the frontend's
    `features/saved-routes/slug.ts`.
    """
    letters = unicodedata.normalize("NFD", name.lower().translate(_PLAIN_LETTERS))
    plain = "".join(c for c in letters if not unicodedata.category(c).startswith("M"))
    stem = _NOT_SLUG.sub("-", plain).strip("-")
    # Cut first, then trim again, so a cut that lands on a dash does not end the name with one.
    stem = stem[:_SLUG_MAX_CHARS].strip("-")
    return stem or f"route-{route_id}"
