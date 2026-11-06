"""Outputs (CRM, .ics, email) and SQLite history. Uses the committed demo history."""
import csv
import datetime as dt
import io

import pytest

from schema.visit_record import VisitRecord
from src.config import ROOT
from src.outputs import CRM_FIELDS, crm_csv, crm_json, followup_email, followup_ics
from src.storage import (
    Metrics, clear_demo, list_visits, mark_followup_done, next_visit_brief, save_approved, visitas_csv,
)

DEMO = [VisitRecord.model_validate_json(l) for l in (ROOT / "data/demo/historial_demo.jsonl").read_text().splitlines() if l]


def by_alert(name):
    return next(r for r in DEMO if getattr(r.alertas, name).detectado)


def test_demo_history_is_approved_and_has_no_patient_data():
    assert len(DEMO) == 19 and all(r.aprobado for r in DEMO)
    blob = "\n".join(r.model_dump_json() for r in DEMO)
    for secret in ["Lucía Ferrer", "4482913", "Pablo Serrano", "18273645", "612 345 678", "Carmen Ruiz", "Javier Ortega"]:
        assert secret not in blob


def test_crm_csv_has_all_fields_and_flags():
    rows = list(csv.DictReader(io.StringIO(crm_csv(DEMO))))
    assert list(rows[0].keys()) == CRM_FIELDS and len(rows) == 19
    ae = by_alert("posible_efecto_adverso")
    row = next(r for r in rows if r["Call_ID"] == ae.visita_id)
    assert row["AE_Flag"] == "True" and row["AE_Reported_To_PV"] == "True"
    assert '"Call_Notes"' in crm_json(ae)


def test_ics_is_valid_all_day_event_with_alarm():
    rec = next(r for r in DEMO if r.fecha_seguimiento)
    ics = followup_ics(rec, "Hospital Demo")
    assert ics.startswith("BEGIN:VCALENDAR\r\n") and ics.endswith("END:VCALENDAR\r\n")
    assert f"DTSTART;VALUE=DATE:{rec.fecha_seguimiento.replace('-', '')}" in ics
    assert "TRIGGER:-P1D" in ics
    assert all(len(l.encode()) <= 75 for l in ics.split("\r\n"))


def test_no_ics_without_date():
    rec = next(r for r in DEMO if not r.fecha_seguimiento)
    assert followup_ics(rec) is None


def test_email_never_mentions_adverse_events_or_answers():
    for r in DEMO:
        mail = followup_email(r).lower()
        assert "adverso" not in mail and "efecto" not in mail and "farmacovigilancia" not in mail
    off = by_alert("pregunta_fuera_ficha")
    assert "información médica" in followup_email(off).lower()


def test_unapproved_record_is_never_saved(tmp_path):
    rec = DEMO[0].model_copy(update={"aprobado": False})
    with pytest.raises(ValueError):
        save_approved(rec, db=tmp_path / "t.db")
    assert list_visits(db=tmp_path / "t.db") == []


def test_history_brief_and_export(tmp_path):
    db = tmp_path / "t.db"
    for r in DEMO:
        save_approved(r, Metrics(10, 60, 0.75, 2), demo=True, db=db)
    assert len(list_visits(db=db)) == 19
    b = next_visit_brief("4", today=dt.date(2026, 12, 31), db=db)
    assert b.n_visitas == 2 and b.ultima.fecha == "2026-11-05"
    assert b.compromisos and all(overdue for _, overdue in b.compromisos if _.fecha_seguimiento)
    assert any(t == "posible efecto adverso" for _, t in b.alertas)
    mark_followup_done(b.compromisos[0][0].visita_id, db=db)
    assert len(next_visit_brief("4", today=dt.date(2026, 12, 31), db=db).compromisos) == len(b.compromisos) - 1
    out = list(csv.DictReader(io.StringIO(visitas_csv(db=db))))
    assert list(out[0].keys()) == ["cuenta_id", "fecha", "segmento", "objetivo_cumplido", "siguiente_paso", "fecha_seguimiento"]
    assert clear_demo(db=db) == 19
