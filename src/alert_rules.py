"""Rule-based safety net for compliance alerts.

Runs locally on the anonymised note, independently of the LLM. The final alert
is LLM OR rules: a small local model can miss a vague adverse event, and for
pharmacovigilance a false positive is cheaper than a missed case.
Rules work sentence by sentence and return the sentence as the fragment.
"""
from __future__ import annotations

import re

_I = re.IGNORECASE

# --- Adverse events --------------------------------------------------------
AE_EXPLICIT = re.compile(
    r"efectos? (adversos?|secundarios?)|reacci[oó]n(es)? adversas?|sobredosis|error de medicaci[oó]n|intoxicaci[oó]n", _I
)
AE_EVENT = re.compile(
    r"insomnio|mareos?|n[aá]useas?|v[oó]mitos?|cefaleas?|dolor de cabeza|somnolencia|sedaci[oó]n|"
    r"(p[eé]rdida|falta) de apetito|(aumento|subida|p[eé]rdida|bajada) de peso|taquicardia|palpitaciones|"
    r"hipertensi[oó]n|convulsi[oó]n(es)?|erupci[oó]n|alergia|picor|ansiedad|irritabilidad|agitaci[oó]n|"
    r"\btics?\b|ideaci[oó]n suicida|suicid\w*|autolesi\w*|urgencias|ingres(o|ó|ar|ado|ada)\b|hospitaliz\w*|"
    r"se (ha )?quej(ado|a|ó)|(se quedó|se ha quedado|está|quedó) embarazada",
    _I,
)
AE_WEAK = re.compile(r"no (les? )?(est[aá] )?funciona(ndo)?|dej[oó] de funcionar|no responden?|empeor\w*|sin efecto|falta de eficacia", _I)
PATIENT_CONTEXT = re.compile(
    r"\bpacientes?\b|\[PACIENTE\]|\bni[ñn][oa]s?\b|\bchic[oa]\b|\bhombre\b|\bmujer\b|\buno\b|\buna\b|su hij[oa]|"
    r"\btras\b|despu[eé]s de|desde que|desde el|al (empezar|iniciar|cambiar)|tratamiento|medicaci[oó]n|tomando",
    _I,
)
TREATMENT_CONTEXT = re.compile(
    r"\btras\b|despu[eé]s de|desde que|desde el|al (empezar|iniciar|cambiar)|tratamiento|medicaci[oó]n|"
    r"cambio de presentaci[oó]n|tomando",
    _I,
)

# --- Possible off-label questions -----------------------------------------
QUESTION = re.compile(r"pregunt\w*|consult\w*|quiere saber|me pide|duda|si hay|si se puede|¿", _I)
OFF_LABEL_TOPIC = re.compile(
    r"dosis|pauta|posolog\w*|menores de|en ni[ñn]os|pedi[aá]tric\w*|embaraz\w*|lactancia|ancian\w*|"
    r"mayores de|combinar|combinaci[oó]n|junto con|asociar|otras? indicaci\w*|uso en|fuera de (ficha|indicaci)|"
    r"datos en|experiencia en|adultos mayores",
    _I,
)

# --- Medical information requests ------------------------------------------
MED_INFO_ACTOR = re.compile(r"\bMedical\b|Informaci[oó]n M[eé]dica|\bMSL\b", _I)
MED_INFO_REQUEST = re.compile(
    r"(me )?pide (el |los |la |las )?(estudios?|datos|publicaci[oó]n\w*|art[ií]culos?|bibliograf[ií]a|evidencia|"
    r"informaci[oó]n cient[ií]fica)",
    _I,
)


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?;])\s+|\s*—\s*", text)
    return [p.strip() for p in parts if p and p.strip()]


def _first(text: str, test) -> str:
    for s in _sentences(text):
        if test(s):
            return s
    return ""


def _ae(s: str) -> bool:
    if AE_EXPLICIT.search(s):
        return True
    if AE_EVENT.search(s) and PATIENT_CONTEXT.search(s):
        return True
    return bool(AE_WEAK.search(s) and TREATMENT_CONTEXT.search(s))


def _off_label(s: str) -> bool:
    return bool(QUESTION.search(s) and OFF_LABEL_TOPIC.search(s))


def _med_info(s: str) -> bool:
    return bool(MED_INFO_ACTOR.search(s) or MED_INFO_REQUEST.search(s))


def detect(text: str) -> dict[str, dict]:
    """Same shape as the LLM's `alertas`: {name: {detectado, fragmento}}."""
    out = {}
    for name, test in (
        ("posible_efecto_adverso", _ae),
        ("pregunta_fuera_ficha", _off_label),
        ("solicitud_informacion_medica", _med_info),
    ):
        frag = _first(text, test)
        out[name] = {"detectado": bool(frag), "fragmento": frag}
    return out
