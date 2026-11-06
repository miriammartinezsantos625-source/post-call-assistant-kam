"""Anonymisation that runs *before* any text reaches the LLM.

Layers, in order:
1. Regex for hard identifiers: DNI/NIE, SIP, medical record number, phone, email,
   date of birth, any long number.
2. Healthcare professionals' names after a title (Dr., Dra., doctor…) -> their role.
3. Person names (spaCy NER candidates + capitalised sequences, filtered by rules)
   -> [PACIENTE] when the context says patient, otherwise [PERSONA].
4. Patient ages ("un niño de 9 años") -> [EDAD].

Returns the clean text plus a report of every substitution, shown to the KAM.
The report stays on the device; only the clean text is sent to the model.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

NAME = r"[A-ZÁÉÍÓÚÑ][a-záéíóúñü]+"
INITIAL = r"[A-ZÁÉÍÓÚÑ]\."
PATIENT_NOUNS = (
    r"paciente|pacientes|niño|niña|chico|chica|hijo|hija|adolescente|bebé|hombre|mujer|"
    r"señor|señora|caso de|madre de|padre de"
)
NUM_WORDS = r"un|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|trece|catorce|quince|dieciséis|diecisiete|dieciocho"

# Hard identifiers. Order matters: labelled numbers before generic ones.
PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    ("Email", "[EMAIL]", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")),
    ("DNI/NIE", "[DNI]", re.compile(r"\b[XYZ]?\d{7,8}[-\s]?[A-HJ-NP-TV-Z]\b", re.IGNORECASE)),
    ("SIP", "[SIP]", re.compile(r"\bSIP\s*:?\s*(?:n[º°o]\.?\s*)?\d{6,10}\b", re.IGNORECASE)),
    ("Historia clínica", "[NHC]", re.compile(
        r"\b(?:NHC|HC|historia(?:\s+cl[ií]nica)?|n[º°o]\.?\s*(?:de\s+)?historia)\s*:?\s*(?:n[º°o]\.?\s*)?\d{4,}\b",
        re.IGNORECASE)),
    ("Fecha de nacimiento", "[FECHA_NAC]", re.compile(
        r"\b(?:nacid[oa]\s+(?:el\s+)?|f\.?\s*nac\.?\s*:?\s*|fecha de nacimiento\s*:?\s*)\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",
        re.IGNORECASE)),
    ("Teléfono", "[TELÉFONO]", re.compile(r"(?<![\d/])(?:\+34[\s-]?)?[6789]\d{2}(?:[\s-]?\d{2,3}){2,3}(?![\d/])")),
    ("Número identificador", "[ID]", re.compile(r"(?<![\d/])\d{6,}(?![\d/])")),
]

# Words the small Spanish NER often mistakes for names.
STOPWORDS = {
    "medical", "market", "access", "marketing", "información", "médica", "farmacovigilancia", "kam",
    "tdah", "usm", "usmia", "pdf", "objetivo", "siguiente", "paso", "vuelvo", "volveré", "comenta",
    "hablamos", "quedamos", "pregunta", "pide", "acepta", "reunión", "farmacia", "hospitalaria",
    "neuropediatra", "psiquiatra", "jefe", "jefa", "servicio", "dirección", "primaria", "urgencias",
    "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo", "enero", "febrero",
    "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre",
    "diciembre", "videollamada", "llamada", "visita", "objeción", "además", "poca", "muy", "le", "me",
    "cerrado", "receptiva", "receptivo", "entonces", "vale", "perfecto", "sí", "no", "ya", "dice",
    "hospital", "centro", "salud", "mental", "unidad", "guía", "comisión", "dr", "dra",
    "paciente", "pacientes", "niño", "niña", "chico", "chica", "hijo", "hija", "madre", "padre", "caso",
}

TITLE_RE = re.compile(rf"\b(?:Dr|Dra|Doctor|Doctora|doctor|doctora)\.?\s+((?:{NAME}|{INITIAL})(?:\s+(?:{NAME}|{INITIAL}|de|del|de la)){{0,3}})")
SEQ_RE = re.compile(rf"\b{NAME}(?:\s+(?:{NAME}|{INITIAL})){{1,3}}")
# Nouns case-insensitive, the name itself must be capitalised.
AFTER_NOUN_RE = re.compile(rf"\b((?i:{PATIENT_NOUNS}))\s*,?\s+({NAME}(?:\s+(?:{NAME}|{INITIAL}))?)")
AGE_RE = re.compile(
    rf"((?:{PATIENT_NOUNS}|\[PACIENTE\])\s*,?\s+)(?:de|con)\s+(?:\d{{1,3}}|{NUM_WORDS})\s+(?:años|meses)",
    re.IGNORECASE,
)


@dataclass
class Replacement:
    tipo: str
    original: str
    sustituto: str


@dataclass
class AnonResult:
    text: str
    replacements: list[Replacement] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.replacements)


@lru_cache(maxsize=1)
def _nlp():
    try:
        import spacy

        return spacy.load("es_core_news_sm", disable=["parser", "lemmatizer"])
    except Exception:  # model not installed: regex layers still run
        return None


def _is_name(span: str) -> bool:
    tokens = [t.strip(".,;:") for t in span.split()]
    tokens = [t for t in tokens if t and t.lower() not in {"de", "del", "la"}]
    if not tokens:
        return False
    return all(t[0].isupper() and t.lower() not in STOPWORDS for t in tokens)


def _patient_context(text: str, start: int, end: int) -> bool:
    before = text[max(0, start - 60):start].lower()
    after = text[end:end + 40].lower()
    return bool(
        re.search(rf"\b({PATIENT_NOUNS})\b", before)
        or re.match(r"\s*,?\s*(de|con)\s+\S+\s+(años|meses)", after)
        or re.search(r"\b(nhc|sip|\[nhc\]|\[sip\])\b", after)
    )


def find_identifiers(text: str) -> list[tuple[str, str]]:
    """Hard identifiers still present in `text` (used as a final guard)."""
    return [(label, m.group(0)) for label, _, p in PATTERNS for m in p.finditer(text)]


def anonymize(text: str, rol: str | None = None) -> AnonResult:
    reps: list[Replacement] = []

    def sub(pattern: re.Pattern[str], tipo: str, repl, s: str) -> str:
        def _r(m: re.Match[str]) -> str:
            new = repl(m) if callable(repl) else repl
            if new != m.group(0):
                reps.append(Replacement(tipo, m.group(0), new))
            return new
        return pattern.sub(_r, s)

    # 1. Hard identifiers
    for label, tag, pattern in PATTERNS:
        text = sub(pattern, label, tag, text)

    # 2. Professionals named after a title -> role
    role_tag = f"[{rol}]" if rol else "[PROFESIONAL]"
    text = sub(TITLE_RE, "Nombre de profesional", role_tag, text)

    # 3. Person names
    text = sub(
        AFTER_NOUN_RE, "Nombre de paciente",
        lambda m: m.group(0) if not _is_name(m.group(2)) else m.group(0).replace(m.group(2), "[PACIENTE]"),
        text,
    )
    candidates: set[str] = {m.group(0) for m in SEQ_RE.finditer(text)}
    nlp = _nlp()
    if nlp is not None:
        candidates |= {e.text for e in nlp(text).ents if e.label_ in ("PER", "LOC", "MISC") and " " in e.text}
    for cand in sorted(candidates, key=len, reverse=True):
        if not _is_name(cand) or cand not in text:
            continue
        for m in list(re.finditer(re.escape(cand), text))[::-1]:
            tag = "[PACIENTE]" if _patient_context(text, m.start(), m.end()) else "[PERSONA]"
            reps.append(Replacement("Nombre de paciente" if tag == "[PACIENTE]" else "Nombre de persona", cand, tag))
            text = text[:m.start()] + tag + text[m.end():]

    # 4. Patient ages (report only the age itself)
    def _age(m: re.Match[str]) -> str:
        reps.append(Replacement("Edad de paciente", m.group(0)[len(m.group(1)):], "[EDAD]"))
        return m.group(1) + "[EDAD]"

    text = AGE_RE.sub(_age, text)

    return AnonResult(text=text, replacements=reps)
