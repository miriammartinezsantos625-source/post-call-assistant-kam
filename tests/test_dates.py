import datetime as dt

import pytest

from src.dates import has_deadline, parse_followup

WED = dt.date(2026, 11, 4)  # miércoles
FRI = dt.date(2026, 11, 6)  # viernes


@pytest.mark.parametrize("expr,visit,expected", [
    ("en tres semanas", WED, "2026-11-25"),
    ("Vuelvo en 3 semanas", WED, "2026-11-25"),
    ("dentro de quince días", WED, "2026-11-19"),
    ("en dos meses", WED, "2027-01-04"),
    ("esta semana", WED, "2026-11-06"),
    ("esta semana", FRI, "2026-11-06"),
    ("la semana que viene", WED, "2026-11-13"),
    ("mañana", WED, "2026-11-05"),
    ("pasado mañana", WED, "2026-11-06"),
    ("el jueves", WED, "2026-11-05"),
    ("el miércoles", WED, "2026-11-11"),
    ("el 15 de diciembre", WED, "2026-12-15"),
    ("el 10 de enero", WED, "2027-01-10"),
])
def test_parse_ok(expr, visit, expected):
    status, d = parse_followup(expr, visit)
    assert status == "ok" and d.isoformat() == expected


@pytest.mark.parametrize("expr", ["el mes que viene", "más adelante", "pronto", "en unos días"])
def test_vague_gives_no_date(expr):
    assert parse_followup(expr, WED) == ("vague", None)


def test_none_and_unparsed():
    assert parse_followup(None, WED) == ("none", None)
    assert parse_followup("cuando termine el congreso", WED)[0] == "unparsed"


@pytest.mark.parametrize("text,expected", [
    ("presentar la actualización de la guía de práctica clínica", False),
    ("conseguir una sesión clínica antes de diciembre", True),
    ("que acepte revisar el protocolo en dos semanas", True),
    ("cerrar fecha para el 15 de enero", True),
])
def test_has_deadline(text, expected):
    assert has_deadline(text) is expected
