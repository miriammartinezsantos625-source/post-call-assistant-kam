"""Deterministic checks on the model output: dates, SMART, missing fields, alerts, summary."""
from __future__ import annotations

import datetime as dt
import re
import uuid

from schema.visit_record import VisitExtraction, VisitRecord
from src.alert_rules import detect as detect_rules
from src.anonymize import AnonResult
from src.config import VisitMeta
from src.dates import has_deadline, parse_followup

RESUMEN_MAX = 400

# Fields that count as "missing" when empty. Lists like materiales_solicitados can
# legitimately be empty, so they are not here.
CORE_FIELDS = [
    "canal",
    "objetivo_visita",
    "objetivo_cumplido",
    "temas_tratados",
    "siguiente_paso",
    "fecha_seguimiento",
    "responsable_siguiente_paso",
    "receptividad",
]

# The app classifies; it never states whether something is on- or off-label.
FORBIDDEN_IN_SUMMARY = re.compile(
    r"(fuera de (?:la )?ficha|off[- ]?label|fuera de indicaci[oó]n|dentro de (?:la )?ficha)", re.I
)

# "evento adverso" without "posible" asserts causality.
UNQUALIFIED_AE = re.compile(
    r"(?<!posible )(?<!posibles )(?:efectos?|eventos?|acontecimientos?|reacci[oó]n(?:es)?) advers[oa]s?", re.I
)

ALERT_MESSAGES = {
    "posible_efecto_adverso": "Notifícalo a Farmacovigilancia según el procedimiento de la compañía (habitualmente en 24 h).",
    "pregunta_fuera_ficha": "Derivar a Medical / Información Médica; no responder en visita.",
    "solicitud_informacion_medica": "Derivar a Medical / Información Médica; no responder en visita.",
}


def _normalise(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower().strip(".,;:\"'“”")


def summary_warnings(resumen: str, objetivo_cumplido: str | None) -> list[str]:
    """Checks on the CRM summary. Re-run live in the review screen as the KAM edits."""
    out = []
    if len(resumen) > RESUMEN_MAX:
        out.append(f"El resumen CRM supera {RESUMEN_MAX} caracteres ({len(resumen)}).")
    if FORBIDDEN_IN_SUMMARY.search(resumen):
        out.append("El resumen CRM valora si algo está dentro o fuera de ficha técnica: eso lo decide Medical. Edítalo.")
    if UNQUALIFIED_AE.search(resumen):
        out.append("El resumen CRM afirma un efecto adverso: escribe 'posible efecto adverso'; la app no valora causalidad.")
    if re.search(r"objetivo (?:cumplido|conseguido|alcanzado)", resumen, re.I) and objetivo_cumplido != "si":
        out.append("El resumen CRM dice que el objetivo se cumplió, pero el campo objetivo_cumplido no lo confirma.")
    return out


def merge_alerts(text: str, llm_alerts: dict, avisos: list[str]) -> dict:
    """Final alert = LLM OR rules. Keeps where each detection came from."""
    rules = detect_rules(text)
    note_norm = _normalise(text)
    merged = {}
    for name, llm in llm_alerts.items():
        rule = rules[name]
        fuente = []
        if llm["detectado"]:
            fuente.append("IA")
            if _normalise(llm["fragmento"]) not in note_norm:
                avisos.append(f"El fragmento de la alerta '{name}' no aparece literalmente en la nota: revísalo.")
        if rule["detectado"]:
            fuente.append("reglas")
        fragmento = llm["fragmento"] if llm["detectado"] else rule["fragmento"]
        otros = []
        if llm["detectado"] and rule["detectado"]:
            r = _normalise(rule["fragmento"])
            if r not in _normalise(llm["fragmento"]) and _normalise(llm["fragmento"]) not in r:
                otros.append(rule["fragmento"])
        merged[name] = {"detectado": bool(fuente), "fragmento": fragmento if fuente else "", "fuente": fuente,
                        "otros_fragmentos": otros}
    return merged


def build_record(text: str, meta: VisitMeta, ext: VisitExtraction, anon: AnonResult | None = None) -> VisitRecord:
    """Merge UI metadata + extraction, run deterministic checks. `text` is the anonymised note."""
    data = ext.model_dump()
    data.pop("parece_conversacion")
    if meta.canal:
        data["canal"] = meta.canal

    avisos: list[str] = []
    if ext.parece_conversacion:
        avisos.append("El texto parece una conversación, no un dictado. Dicta tu resumen después de la visita.")

    data["alertas"] = merge_alerts(text, data["alertas"], avisos)

    # Follow-up date: computed here from the literal expression, not by the model.
    visit = dt.date.fromisoformat(meta.fecha)
    status, fecha = parse_followup(data["fecha_seguimiento_expresion"], visit)
    if status == "ok":
        data["fecha_seguimiento"] = fecha.isoformat()
    elif status in ("vague", "none"):
        data["fecha_seguimiento"] = None
    elif data["fecha_seguimiento"]:  # unparsed expression: keep the model's date, flagged
        try:
            if dt.date.fromisoformat(data["fecha_seguimiento"]) < visit:
                raise ValueError
            avisos.append(
                f"Fecha de seguimiento calculada por la IA a partir de "
                f"'{data['fecha_seguimiento_expresion']}': revísala."
            )
        except ValueError:
            avisos.append(f"Fecha de seguimiento no válida ('{data['fecha_seguimiento']}'); se deja vacía.")
            data["fecha_seguimiento"] = None

    # SMART: no objective -> no evaluation; deadline checked against the objective text.
    smart = data["objetivo_smart"]
    if not data["objetivo_visita"]:
        data["objetivo_smart"] = None
    elif smart:
        plazo = has_deadline(data["objetivo_visita"])
        smart["con_plazo"] = plazo
        smart["que_falta"] = [q for q in smart["que_falta"] if "plazo" not in q.lower()]
        if not plazo:
            smart["que_falta"].append("no incluye un plazo")

    # CRM summary: length and compliance wording.
    avisos += summary_warnings(data["resumen_crm"], data["objetivo_cumplido"])

    # Missing fields: deterministic check, merged with what the model listed.
    def empty(field: str) -> bool:
        v = data[field]
        if field == "receptividad":
            return v["valor_1_5"] is None
        return v is None or v == [] or v == ""

    valid = set(VisitExtraction.model_fields) - {"parece_conversacion", "objetivo_smart", "campos_faltantes"}
    faltan = [f for f in CORE_FIELDS if empty(f)]
    faltan += [f for f in ext.campos_faltantes if f in valid and f not in faltan and empty(f)]
    data["campos_faltantes"] = faltan

    if anon and anon.changed:
        avisos.append(f"Se han anonimizado {len(anon.replacements)} datos personales antes de procesar la nota.")

    return VisitRecord(
        visita_id=str(uuid.uuid4()),
        fecha=meta.fecha,
        cuenta_id=str(meta.cuenta_id),
        segmento=meta.segmento,
        interlocutor_rol=meta.interlocutor_rol,
        avisos_validacion=avisos,
        anonimizacion=[{"tipo": r.tipo, "sustituto": r.sustituto} for r in (anon.replacements if anon else [])],
        **data,
    )


def fields_filled_ratio(rec: VisitRecord) -> float:
    """Share of core fields the pipeline filled automatically."""
    return 1 - len([f for f in rec.campos_faltantes if f in CORE_FIELDS]) / len(CORE_FIELDS)
