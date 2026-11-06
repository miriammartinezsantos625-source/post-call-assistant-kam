"""Weekly dashboard: aggregates over approved visits, and the aggregated-only manager report.

The AI report receives only counts and categories built here (no account names, no notes, no
summaries, no people). The exact payload is shown in the UI before anything is generated.
"""
from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

from src.config import ROOT, load_config
from src.storage import list_visits, record_of

SEGMENTS = ["A", "B", "C"]
ALERT_LABELS = {
    "posible_efecto_adverso": "Posible efecto adverso (Farmacovigilancia)",
    "pregunta_fuera_ficha": "Pregunta fuera de ficha (Medical)",
    "solicitud_informacion_medica": "Solicitud de información médica (Medical)",
}


def _none(v):
    """pandas turns missing values into NaN; the UI and the report expect None."""
    return None if v is None or (isinstance(v, float) and pd.isna(v)) else v


def week_start(d: dt.date) -> dt.date:
    return d - dt.timedelta(days=d.weekday())


def load_plan(path: Path | None = None) -> dict[str, int]:
    """Weekly visit plan per segment (Territory Scope's plan when available)."""
    path = path or ROOT / load_config()["data"].get("plan_csv", "data/demo/plan_semanal.csv")
    if not Path(path).exists():
        return {}
    df = pd.read_csv(path, dtype={"segmento": str})
    return {r.segmento: int(r.visitas_semana) for r in df.itertuples()}


def visits_frame(db: Path | None = None) -> pd.DataFrame:
    rows = []
    for row in list_visits(db=db):
        rec = record_of(row)
        rows.append({
            "visita_id": rec.visita_id, "fecha": dt.date.fromisoformat(rec.fecha), "cuenta_id": rec.cuenta_id,
            "segmento": rec.segmento or "—", "objetivo_cumplido": rec.objetivo_cumplido or "sin dato",
            "siguiente_paso": rec.siguiente_paso, "fecha_seguimiento": rec.fecha_seguimiento,
            "responsable": rec.responsable_siguiente_paso, "hecho": bool(row["seguimiento_hecho"]),
            "objeciones": [o.tipo for o in rec.objeciones],
            "alertas": [k for k, v in rec.alertas.model_dump().items() if v["detectado"]],
            "alertas_confirmadas": [k for k, v in rec.alertas.model_dump().items() if v["detectado"] and v["confirmado_por_kam"]],
            "segundos_total": row["segundos_total"], "campos_auto": row["campos_auto"],
        })
    return pd.DataFrame(rows)


def available_weeks(df: pd.DataFrame) -> list[dt.date]:
    return sorted({week_start(d) for d in df["fecha"]}, reverse=True) if not df.empty else []


@dataclass
class WeekSummary:
    semana: str
    visitas: int
    visitas_por_segmento: dict[str, int]
    plan_por_segmento: dict[str, int]
    objetivos: dict[str, int]
    objeciones_por_tipo: dict[str, int]
    seguimientos_pendientes: int
    seguimientos_vencidos: int
    alertas_detectadas: dict[str, int]
    alertas_confirmadas: int
    alertas_total: int
    cuentas_visitadas: int
    mediana_segundos_nota_a_ficha: float | None = None
    campos_auto_media: float | None = None
    pendientes: list[dict] = field(default_factory=list)   # for the UI table only — never sent to the model

    def cumplimiento_objetivos(self) -> float | None:
        """Share of the week's visits with the objective confirmed as met (visits without data count as not confirmed)."""
        return None if not self.visitas else self.objetivos.get("si", 0) / self.visitas

    def report_payload(self) -> dict:
        """Exactly what the AI report receives: aggregated numbers and categories only."""
        d = asdict(self)
        d.pop("pendientes")
        d["objetivo_cumplido_confirmado_pct_sobre_visitas"] = None if self.cumplimiento_objetivos() is None else round(100 * self.cumplimiento_objetivos())
        return d


def summarize(df: pd.DataFrame, monday: dt.date, today: dt.date | None = None, plan: dict[str, int] | None = None) -> WeekSummary:
    today = today or dt.date.today()
    plan = plan if plan is not None else load_plan()
    week = df[(df["fecha"] >= monday) & (df["fecha"] < monday + dt.timedelta(days=7))] if not df.empty else df
    # follow-ups are a running list: everything still open up to the end of the week
    open_ = df[df["siguiente_paso"].notna() & ~df["hecho"] & (df["fecha"] < monday + dt.timedelta(days=7))] if not df.empty else df
    overdue = open_[open_["fecha_seguimiento"].notna() & (open_["fecha_seguimiento"].astype(str) < today.isoformat())] if not open_.empty else open_
    alerts = Counter(a for lst in week.get("alertas", []) for a in lst)
    confirmed = sum(len(lst) for lst in week.get("alertas_confirmadas", []))
    times = week["segundos_total"].dropna() if not week.empty else pd.Series(dtype=float)
    autos = week["campos_auto"].dropna() if not week.empty else pd.Series(dtype=float)
    return WeekSummary(
        semana=f"{monday:%d/%m/%Y} – {monday + dt.timedelta(days=6):%d/%m/%Y}",
        visitas=len(week),
        visitas_por_segmento={s: int((week["segmento"] == s).sum()) for s in SEGMENTS} if not week.empty else {s: 0 for s in SEGMENTS},
        plan_por_segmento={s: plan.get(s, 0) for s in SEGMENTS},
        objetivos={k: int((week["objetivo_cumplido"] == k).sum()) for k in ("si", "parcial", "no", "sin dato")} if not week.empty else {},
        objeciones_por_tipo=dict(Counter(t for lst in week.get("objeciones", []) for t in lst).most_common()),
        seguimientos_pendientes=len(open_),
        seguimientos_vencidos=len(overdue),
        alertas_detectadas={ALERT_LABELS[k]: alerts.get(k, 0) for k in ALERT_LABELS},
        alertas_confirmadas=confirmed,
        alertas_total=sum(alerts.values()),
        cuentas_visitadas=int(week["cuenta_id"].nunique()) if not week.empty else 0,
        mediana_segundos_nota_a_ficha=None if times.empty else float(times.median()),
        campos_auto_media=None if autos.empty else float(autos.mean()),
        pendientes=[
            {"cuenta_id": r.cuenta_id, "siguiente_paso": r.siguiente_paso, "responsable": _none(r.responsable),
             "fecha_seguimiento": _none(r.fecha_seguimiento), "vencido": r.visita_id in set(overdue["visita_id"])}
            for r in open_.sort_values("fecha_seguimiento", na_position="last").itertuples()
        ],
    )


REPORT_SYSTEM = """Eres un asistente que redacta el informe semanal de una Key Account Manager de neurociencias para su manager.
Recibes SOLO datos agregados en JSON (recuentos y categorías). Reglas:
- Usa únicamente esas cifras; no inventes datos, nombres, cuentas, productos ni causas.
- Máximo 170 palabras, en español, tono profesional y neutro, en Markdown con estas secciones:
  **Cobertura** (visitas frente al plan por segmento), **Resultados** (objetivos y objeciones más frecuentes),
  **Seguimiento** (pendientes y vencidos), **Compliance** (alertas detectadas y confirmadas) y
  **Foco para la próxima semana** (2 o 3 puntos que se deduzcan directamente de las cifras).
- No valores ni interpretes las alertas clínicamente: solo indica cuántas hubo y si se confirmaron.
- Las visitas «sin dato» de objetivo son fichas en las que la KAM no registró el resultado (un tema de registro),
  no cuentas que no respondieron. Habla de visitas, nunca de cuentas, al dar esas cifras.
- Las objeciones científicas y las preguntas fuera de ficha se derivan a Medical: no propongas que la KAM prepare
  respuestas propias para ellas."""


def generate_report(summary: WeekSummary, llm_cfg: dict | None = None) -> str:
    from src.llm import generate_text

    payload = json.dumps(summary.report_payload(), ensure_ascii=False, indent=1)
    return generate_text(REPORT_SYSTEM, f"Datos agregados de la semana:\n```json\n{payload}\n```", llm_cfg)
