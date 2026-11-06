"""Deterministic Spanish date expressions -> follow-up date.

The LLM only copies the literal expression ("en tres semanas"); the date
arithmetic happens here, because small local models get it wrong.
"""
from __future__ import annotations

import calendar
import datetime as dt
import re
import unicodedata

NUMS = {
    "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
    "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "quince": 15,
    "veinte": 20, "treinta": 30,
}
DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
VAGUE = re.compile(
    r"\b(el mes que viene|el proximo mes|el mes proximo|mas adelante|pronto|en breve|"
    r"en unos dias|en unas semanas|proximamente|cuando pueda|a la vuelta)\b"
)

# Something that looks like a deadline, for the SMART "con plazo" check.
HAS_DEADLINE = re.compile(
    r"\b(antes de|para el|para finales|a finales|hasta el|esta semana|este mes|este trimestre|"
    r"en (un|una|dos|tres|cuatro|cinco|seis|\d+) (dias?|semanas?|meses?)|"
    r"(primer|segundo|tercer|cuarto) trimestre|q[1-4]|\d{1,2}/\d{1,2}|"
    r"\d{1,2} de (" + "|".join(MESES) + r"))\b"
)


def _plain(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _add_months(d: dt.date, n: int) -> dt.date:
    y, m = divmod(d.month - 1 + n, 12)
    y, m = d.year + y, m + 1
    return d.replace(year=y, month=m, day=min(d.day, calendar.monthrange(y, m)[1]))


def _num(tok: str) -> int | None:
    return int(tok) if tok.isdigit() else NUMS.get(tok)


def parse_followup(expr: str | None, visit: dt.date) -> tuple[str, dt.date | None]:
    """Return (status, date). status: 'ok' | 'vague' | 'unparsed' | 'none'."""
    if not expr:
        return "none", None
    e = _plain(expr)
    if VAGUE.search(e):
        return "vague", None

    if re.search(r"\bpasado manana\b", e):
        return "ok", visit + dt.timedelta(days=2)
    if re.search(r"\bmanana\b", e):
        return "ok", visit + dt.timedelta(days=1)
    if re.search(r"\bhoy\b", e):
        return "ok", visit

    m = re.search(r"\b(?:en|dentro de)\s+(\w+)\s+(dias?|semanas?|mes(?:es)?|quincenas?)\b", e)
    if m and (n := _num(m.group(1))):
        unit = m.group(2)
        if unit.startswith("dia"):
            return "ok", visit + dt.timedelta(days=n)
        if unit.startswith("semana"):
            return "ok", visit + dt.timedelta(weeks=n)
        if unit.startswith("quincena"):
            return "ok", visit + dt.timedelta(days=15 * n)
        return "ok", _add_months(visit, n)

    friday = visit + dt.timedelta(days=4 - visit.weekday())
    if re.search(r"\besta semana\b", e):
        return "ok", max(visit, friday)
    if re.search(r"\b(la semana que viene|la proxima semana|la semana proxima)\b", e):
        return "ok", friday + dt.timedelta(weeks=1)

    m = re.search(r"\b(\d{1,2}) de (" + "|".join(MESES) + r")\b", e)
    if m:
        day, month = int(m.group(1)), MESES.index(m.group(2)) + 1
        try:
            d = dt.date(visit.year, month, day)
            return "ok", d if d >= visit else d.replace(year=visit.year + 1)
        except ValueError:
            return "unparsed", None

    m = re.search(r"\b(" + "|".join(DIAS) + r")\b", e)
    if m:
        target = DIAS.index(m.group(1))
        ahead = (target - visit.weekday()) % 7 or 7  # next occurrence after the visit
        return "ok", visit + dt.timedelta(days=ahead)

    return "unparsed", None


def has_deadline(text: str | None) -> bool:
    return bool(text) and bool(HAS_DEADLINE.search(_plain(text)))
