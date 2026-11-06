"""Weekly dashboard aggregates, the aggregated-only report payload, and the public demo mode."""
import datetime as dt
import json

import pytest
from streamlit.testing.v1 import AppTest

import src.storage as storage
from schema.visit_record import VisitRecord
from src.config import ROOT, VisitMeta
from src.weekly import available_weeks, summarize, visits_frame

DEMO = [VisitRecord.model_validate_json(l) for l in (ROOT / "data/demo/historial_demo.jsonl").read_text().splitlines() if l]


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "v.db"
    monkeypatch.setattr(storage, "DEFAULT_DB", path)
    for r in DEMO:
        storage.save_approved(r, demo=True)
    return path


def test_weekly_summary_counts(db):
    df = visits_frame()
    weeks = available_weeks(df)
    assert weeks == [dt.date(2026, 11, 2), dt.date(2026, 10, 26)]
    s = summarize(df, weeks[0], today=dt.date(2026, 11, 6), plan={"A": 5, "B": 4, "C": 2})
    assert s.visitas == sum(s.visitas_por_segmento.values()) == 12
    assert all(isinstance(p['fecha_seguimiento'], (str, type(None))) for p in s.pendientes)
    assert s.alertas_confirmadas == s.alertas_total
    assert 0 < s.seguimientos_vencidos <= s.seguimientos_pendientes
    assert s.cumplimiento_objetivos() == s.objetivos["si"] / s.visitas   # visits without data are not counted as met


def test_report_payload_has_no_free_text_or_identifiers(db):
    df = visits_frame()
    s = summarize(df, available_weeks(df)[0], today=dt.date(2026, 11, 6))
    blob = json.dumps(s.report_payload(), ensure_ascii=False)
    assert "pendientes" not in s.report_payload()
    for r in DEMO:                                   # no summaries, next steps, fragments or account ids leak in
        assert r.resumen_crm not in blob
        if r.siguiente_paso:
            assert r.siguiente_paso not in blob
    assert "cuenta_id" not in blob and "Hospital" not in blob


def test_demo_provider_replays_synthetic_notes_and_refuses_others(monkeypatch):
    import csv

    from src.llm import LLMOutputError
    from src.structure import process_note

    monkeypatch.setenv("POSTCALL_DEMO", "1")
    rows = [r for r in csv.DictReader(open(ROOT / "data/demo/notas_sinteticas.csv", encoding="utf-8")) if r["esperado_conversacion"] != "true"]
    for r in rows:
        rec = process_note(r["texto"], VisitMeta(r["cuenta_id"], r["interlocutor_rol"], r["fecha"])).record
        assert rec.alertas.posible_efecto_adverso.detectado == (r["esperado_efecto_adverso"] == "true")
    with pytest.raises(LLMOutputError):
        process_note("Una nota cualquiera que no es de la demo.", VisitMeta("3", "otro", "2026-11-06"))


def test_demo_app_end_to_end(monkeypatch, tmp_path):
    monkeypatch.setenv("POSTCALL_DEMO", "1")
    monkeypatch.setattr(storage, "DEFAULT_DB", tmp_path / "v.db")
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    assert not at.exception, at.exception
    assert len(storage.list_visits()) == 19                    # history seeded for the public demo
    at.selectbox(key="nv_ejemplo").select("N09").run()
    next(b for b in at.button if b.label == "Generar ficha").click().run()
    assert not at.exception, at.exception
    assert any(c.label == "He notificado a Farmacovigilancia" for c in at.checkbox)
