"""Offline tests (no API calls)."""
import pytest

from schema.visit_record import VisitExtraction
from src.structure import UnsafeTextError, VisitMeta, build_record, extract

META = VisitMeta(cuenta_id="4", interlocutor_rol="jefe de servicio", fecha="2026-11-05", segmento="A", canal="presencial")
NOTE = "Comenta que un paciente suyo tuvo insomnio y pérdida de apetito tras empezar el tratamiento."


def fake_extraction(**over):
    base = dict(
        parece_conversacion=False, canal=None, objetivo_visita=None, objetivo_smart=None,
        objetivo_cumplido=None, temas_tratados=["circuitos de derivación"], necesidades_detectadas=[],
        objeciones=[], materiales_solicitados=[], siguiente_paso="Hablar de circuitos con primaria",
        fecha_seguimiento=None, fecha_seguimiento_expresion="el mes que viene",
        responsable_siguiente_paso="KAM", receptividad={"valor_1_5": None, "motivo": None},
        colaboracion_transversal=[],
        alertas={
            "posible_efecto_adverso": {"detectado": True, "fragmento": "un paciente suyo tuvo insomnio y pérdida de apetito tras empezar el tratamiento"},
            "pregunta_fuera_ficha": {"detectado": False, "fragmento": ""},
            "solicitud_informacion_medica": {"detectado": False, "fragmento": ""},
        },
        campos_faltantes=["objetivo_visita"], resumen_crm="Se registra posible efecto adverso para su notificación.",
    )
    base.update(over)
    return VisitExtraction.model_validate(base)


def test_schema_is_json_serialisable():
    s = VisitExtraction.model_json_schema()
    assert "alertas" in s["properties"]


def test_guard_blocks_identifiers_before_any_call():
    with pytest.raises(UnsafeTextError):
        extract("Paciente con DNI 12345678Z refiere mareos.", META, llm_cfg={"provider": "none"})


def test_record_merges_meta_and_computes_missing():
    rec = build_record(NOTE, META, fake_extraction())
    assert rec.canal == "presencial"  # from UI
    assert rec.segmento == "A"
    assert "fecha_seguimiento" in rec.campos_faltantes
    assert "objetivo_visita" in rec.campos_faltantes
    assert "canal" not in rec.campos_faltantes
    assert rec.avisos_validacion == []
    assert rec.aprobado is False


def test_non_literal_fragment_is_flagged():
    ext = fake_extraction(alertas={
        "posible_efecto_adverso": {"detectado": True, "fragmento": "el paciente presentó insomnio grave"},
        "pregunta_fuera_ficha": {"detectado": False, "fragmento": ""},
        "solicitud_informacion_medica": {"detectado": False, "fragmento": ""},
    })
    rec = build_record(NOTE, META, ext)
    assert any("no aparece literalmente" in a for a in rec.avisos_validacion)


def test_bad_date_is_cleared():
    rec = build_record(NOTE, META, fake_extraction(fecha_seguimiento="pronto"))
    assert rec.fecha_seguimiento is None


def test_followup_date_computed_from_expression_not_model():
    ext = fake_extraction(fecha_seguimiento="2026-11-09", fecha_seguimiento_expresion="esta semana")
    rec = build_record(NOTE, META, ext)  # visit Thu 2026-11-05
    assert rec.fecha_seguimiento == "2026-11-06"


def test_vague_expression_clears_model_date():
    rec = build_record(NOTE, META, fake_extraction(fecha_seguimiento="2026-12-05"))  # "el mes que viene"
    assert rec.fecha_seguimiento is None and "fecha_seguimiento" in rec.campos_faltantes


def test_no_objective_means_no_smart():
    smart = {"especifico": False, "medible": False, "con_plazo": True, "que_falta": []}
    rec = build_record(NOTE, META, fake_extraction(objetivo_smart=smart))
    assert rec.objetivo_smart is None


def test_smart_deadline_is_deterministic():
    smart = {"especifico": True, "medible": True, "con_plazo": True, "que_falta": []}
    rec = build_record(NOTE, META, fake_extraction(objetivo_visita="presentar la guía", objetivo_smart=smart))
    assert rec.objetivo_smart.con_plazo is False
    assert "no incluye un plazo" in rec.objetivo_smart.que_falta


def test_summary_judging_label_is_flagged():
    rec = build_record(NOTE, META, fake_extraction(resumen_crm="Pregunta que queda fuera de ficha técnica."))
    assert any("Medical" in a for a in rec.avisos_validacion)


def test_summary_claiming_success_without_field_is_flagged():
    rec = build_record(NOTE, META, fake_extraction(resumen_crm="Objetivo cumplido."))
    assert any("objetivo_cumplido" in a for a in rec.avisos_validacion)


@pytest.mark.parametrize("resumen,flagged", [
    ("Se reporta evento adverso (taquicardia) ya resuelto.", True),
    ("Se reportan efectos adversos (mareos) en paciente actual.", True),
    ("Se registra posible efecto adverso para su notificación.", False),
    ("Se registran posibles efectos adversos.", False),
])
def test_summary_must_say_possible_adverse_event(resumen, flagged):
    rec = build_record(NOTE, META, fake_extraction(resumen_crm=resumen))
    assert any("posible efecto adverso" in a for a in rec.avisos_validacion) is flagged


def test_rules_fragment_kept_when_llm_quotes_another_sentence():
    note = "Me ha pedido el resumen de la guía en PDF. Le digo que lo he trasladado a Medical."
    ext = fake_extraction(alertas={
        "posible_efecto_adverso": {"detectado": False, "fragmento": ""},
        "pregunta_fuera_ficha": {"detectado": False, "fragmento": ""},
        "solicitud_informacion_medica": {"detectado": True, "fragmento": "Me ha pedido el resumen de la guía en PDF."},
    }, resumen_crm="Visita.")
    al = build_record(note, META, ext).alertas.solicitud_informacion_medica
    assert al.fuente == ["IA", "reglas"]
    assert al.otros_fragmentos == ["Le digo que lo he trasladado a Medical."]
