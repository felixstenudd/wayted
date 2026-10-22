import pytest

from app.logbook.routes.export import slug

# The same cases as frontend/src/features/saved-routes/slug.test.ts: both sides name files alike.
CASES = [
    ("Morning loop", "morning-loop"),
    ("Södermalm", "sodermalm"),
    ("Crème brûlée à Ærø", "creme-brulee-a-aero"),
    ("Øresund runda", "oresund-runda"),
    ("Strandstraße", "strandstrasse"),
    ("Łódź", "lodz"),
    ("Œuvre Æbeltoft", "oeuvre-aebeltoft"),
    ("Đakovo Þórsmörk Ðorđe", "dakovo-thorsmork-dorde"),
    ("Kırkpınar", "kirkpinar"),
    ("  Runt Årstaviken, 2 varv!! ", "runt-arstaviken-2-varv"),
    ("Hill #3 / (fast)", "hill-3-fast"),
    ("a" * 70, "a" * 60),
    # The cut lands on a dash, which is trimmed.
    ("word " * 20, "-".join(["word"] * 12)),
    ("!!!", "route-7"),
    ("東京の道", "route-7"),
]


@pytest.mark.parametrize(("name", "expected"), CASES)
def test_route_names_become_plain_file_names(name: str, expected: str) -> None:
    assert slug(name, 7) == expected
