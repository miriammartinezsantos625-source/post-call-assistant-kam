"""Local SQLite history. Only records the KAM has approved are ever written."""
from __future__ import annotations

import csv
import datetime as dt
import io
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from schema.visit_record import VisitRecord
from src.config import ROOT

DEFAULT_DB = ROOT / "data" / "local" / "visitas.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS visitas (
    visita_id TEXT PRIMARY KEY,
    cuenta_id TEXT NOT NULL,
    fecha TEXT NOT NULL,
    segmento TEXT,
    interlocutor_rol TEXT,
    objetivo_cumplido TEXT,
    siguiente_paso TEXT,
    fecha_seguimiento TEXT,
    responsable TEXT,
    alerta_ea INTEGER, alerta_ff INTEGER, alerta_im INTEGER,
    record_json TEXT NOT NULL,
    aprobado_en TEXT NOT NULL,
    segundos_proceso REAL,
    segundos_total REAL,
    campos_auto REAL,
    campos_editados INTEGER,
    seguimiento_hecho INTEGER DEFAULT 0,
    demo INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_visitas_cuenta ON visitas(cuenta_id, fecha);
"""


@dataclass
class Metrics:
    segundos_proceso: float | None = None   # note -> proposed record
    segundos_total: float | None = None     # "Procesar" click -> "Aprobar" click
    campos_auto: float | None = None        # share of core fields filled by the pipeline
    campos_editados: int | None = None      # fields the KAM changed before approving


@contextmanager
def connect(db: Path | None = None):
    db = Path(db or DEFAULT_DB)
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def save_approved(rec: VisitRecord, m: Metrics | None = None, demo: bool = False, db: Path | None = None) -> None:
    if not rec.aprobado:
        raise ValueError("Solo se guardan fichas aprobadas por la KAM.")
    m = m or Metrics()
    a = rec.alertas
    with connect(db) as con:
        con.execute(
            "INSERT OR REPLACE INTO visitas VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rec.visita_id, rec.cuenta_id, rec.fecha, rec.segmento, rec.interlocutor_rol, rec.objetivo_cumplido,
             rec.siguiente_paso, rec.fecha_seguimiento, rec.responsable_siguiente_paso,
             int(a.posible_efecto_adverso.detectado), int(a.pregunta_fuera_ficha.detectado),
             int(a.solicitud_informacion_medica.detectado), rec.model_dump_json(),
             dt.datetime.now().isoformat(timespec="seconds"), m.segundos_proceso, m.segundos_total,
             m.campos_auto, m.campos_editados, 0, int(demo)),
        )


def list_visits(cuenta_id: str | None = None, db: Path | None = None) -> list[sqlite3.Row]:
    with connect(db) as con:
        q = "SELECT * FROM visitas" + (" WHERE cuenta_id = ?" if cuenta_id else "") + " ORDER BY fecha DESC, aprobado_en DESC"
        return con.execute(q, (cuenta_id,) if cuenta_id else ()).fetchall()


def record_of(row: sqlite3.Row) -> VisitRecord:
    return VisitRecord.model_validate_json(row["record_json"])


def mark_followup_done(visita_id: str, done: bool = True, db: Path | None = None) -> None:
    with connect(db) as con:
        con.execute("UPDATE visitas SET seguimiento_hecho = ? WHERE visita_id = ?", (int(done), visita_id))


def clear_demo(db: Path | None = None) -> int:
    with connect(db) as con:
        return con.execute("DELETE FROM visitas WHERE demo = 1").rowcount


def visitas_csv(db: Path | None = None) -> str:
    """Export for Territory Scope (same cuenta_id key)."""
    cols = ["cuenta_id", "fecha", "segmento", "objetivo_cumplido", "siguiente_paso", "fecha_seguimiento"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for r in sorted(list_visits(db=db), key=lambda r: (r["fecha"], r["cuenta_id"])):
        w.writerow([r[c] or "" for c in cols])
    return buf.getvalue()


# ---------------------------------------------------------------- next-visit brief
@dataclass
class Brief:
    ultima: VisitRecord | None
    compromisos: list[tuple[VisitRecord, bool]]  # (record, overdue)
    objeciones: list[tuple[str, str, str]]       # (fecha, tipo, texto)
    materiales: list[tuple[str, str]]            # (fecha, material)
    alertas: list[tuple[str, str]]               # (fecha, tipo)
    n_visitas: int


def next_visit_brief(cuenta_id: str, today: dt.date | None = None, db: Path | None = None, last_n: int = 3) -> Brief:
    """Deterministic: built from approved records only, no model involved."""
    today = today or dt.date.today()
    rows = list_visits(cuenta_id, db)
    recs = [(r, record_of(r)) for r in rows]
    compromisos = [
        (rec, bool(rec.fecha_seguimiento and dt.date.fromisoformat(rec.fecha_seguimiento) < today))
        for row, rec in recs if rec.siguiente_paso and not row["seguimiento_hecho"]
    ]
    recent = [rec for _, rec in recs[:last_n]]
    labels = {"posible_efecto_adverso": "posible efecto adverso", "pregunta_fuera_ficha": "pregunta derivada a Medical",
              "solicitud_informacion_medica": "solicitud de información médica"}
    return Brief(
        ultima=recs[0][1] if recs else None,
        compromisos=compromisos,
        objeciones=[(r.fecha, o.tipo, o.texto) for r in recent for o in r.objeciones],
        materiales=[(r.fecha, m) for r in recent for m in r.materiales_solicitados],
        alertas=[(r.fecha, labels[k]) for r in recent for k, v in r.alertas.model_dump().items() if v["detectado"]],
        n_visitas=len(recs),
    )
