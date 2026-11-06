"""End-to-end UI tests with Streamlit AppTest (no browser; the LLM is replaced by a fixed answer)."""
import pytest
from streamlit.testing.v1 import AppTest

import src.storage as storage
import src.structure as structure
from schema.visit_record import VisitExtraction
from src.config import ROOT

NO_ALERTS = {k: {"detectado": False, "fragmento": ""}
             for k in ("posible_efecto_adverso", "pregunta_fuera_ficha", "solicitud_informacion_medica")}


def extraction(**over) -> VisitExtraction:
    base = dict(
        parece_conversacion=False, canal=None, objetivo_visita=None, objetivo_smart=None, objetivo_cumplido=None,
        temas_tratados=["circuitos de derivación"], necesidades_detectadas=[], objeciones=[], materiales_solicitados=[],
        siguiente_paso="Hablar de circuitos de derivación con primaria", fecha_seguimiento=None,
        fecha_seguimiento_expresion="el mes que viene", responsable_siguiente_paso="KAM",
        receptividad={"valor_1_5": None, "motivo": None}, colaboracion_transversal=[],
        alertas={**NO_ALERTS, "posible_efecto_adverso": {
            "detectado": True, "fragmento": "un paciente suyo tuvo insomnio y pérdida de apetito tras empezar el tratamiento"}},
        campos_faltantes=[], resumen_crm="Se registra posible efecto adverso para su notificación a Farmacovigilancia.",
    )
    base.update(over)
    return VisitExtraction.model_validate(base)


class FakeLLM:
    def __init__(self):
        self.ext = extraction()
        self.calls: list[str] = []

    def __call__(self, system, user, cfg):
        self.calls.append(user)
        return self.ext


@pytest.fixture
def fake(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "DEFAULT_DB", tmp_path / "visitas.db")
    llm = FakeLLM()
    monkeypatch.setattr(structure, "call_llm", llm)
    return llm


@pytest.fixture
def at(fake):
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    app.run()
    assert not app.exception, app.exception
    return app


def button(at, label):
    return next(b for b in at.button if b.label == label)


def generate(at, nota_id):
    at.selectbox(key="nv_ejemplo").select(nota_id).run()
    button(at, "Generar ficha").click().run()
    assert not at.exception, at.exception


def test_home_renders_with_reminder(at):
    md = " ".join(m.value for m in at.markdown)
    assert "No grabes la conversación" in md and "Del dictado a la" in md


def test_empty_note_is_refused_without_calling_the_model(at, fake):
    button(at, "Generar ficha").click().run()
    assert any("Escribe, dicta o sube" in e.value for e in at.error)
    assert fake.calls == []


def test_conversation_is_rejected_before_the_model(at, fake):
    at.text_area(key="nv_texto").input(
        "—¿Y para cuándo tendríais el material? —Pues en dos semanas. —Vale, perfecto, te escribo.").run()
    button(at, "Generar ficha").click().run()
    assert any("conversación" in e.value for e in at.error)
    assert fake.calls == []


def test_patient_data_never_reaches_the_model(at, fake):
    generate(at, "N09")
    sent = fake.calls[0]
    for secret in ["Lucía Ferrer", "4482913", "11 años"]:
        assert secret not in sent
    assert "[PACIENTE]" in sent


def test_alert_blocks_approval_until_confirmed_and_nothing_is_saved_before(at):
    generate(at, "N02")
    assert button(at, "Aprobar y guardar").disabled
    assert storage.list_visits() == []

    next(c for c in at.checkbox if c.label == "He notificado a Farmacovigilancia").check().run()
    assert not button(at, "Aprobar y guardar").disabled
    button(at, "Aprobar y guardar").click().run()
    assert not at.exception, at.exception

    rows = storage.list_visits()
    assert len(rows) == 1
    rec = storage.record_of(rows[0])
    assert rec.aprobado and rec.alertas.posible_efecto_adverso.confirmado_por_kam
    assert rec.fecha_seguimiento is None and "fecha_seguimiento" in rec.campos_faltantes
    assert any("aprobada" in m.value for m in at.markdown)        # outputs screen


def test_long_summary_is_not_truncated_and_blocks_approval(at, fake):
    long = ("Resumen largo de la visita con mucho detalle. " * 12).strip()
    assert len(long) > 400
    fake.ext = extraction(resumen_crm=long, alertas=NO_ALERTS)
    generate(at, "N04")
    summary = next(t for t in at.text_area if t.value.startswith("Resumen largo"))
    assert summary.value == long                                   # not silently cut to 400
    assert button(at, "Aprobar y guardar").disabled

    summary.input("Resumen corto y neutro de la visita.").run()
    assert not button(at, "Aprobar y guardar").disabled


def test_unexpected_model_values_do_not_crash_review(at, fake):
    ext = extraction()
    object.__setattr__(ext.receptividad, "valor_1_5", 9)          # out of range from a misbehaving model
    fake.ext = ext
    generate(at, "N02")
    assert any(b.label == "Aprobar y guardar" for b in at.button)
