"""Pipeline: KAM note -> anonymise -> guard -> LLM -> validated visit record."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from schema.visit_record import VisitExtraction, VisitRecord
from src.anonymize import AnonResult, anonymize, find_identifiers
from src.config import ROOT, VisitMeta, load_config
from src.conversation import looks_like_conversation
from src.llm import call_llm
from src.validate import build_record

SYSTEM_PROMPT = (ROOT / "prompts" / "system_prompt.md").read_text(encoding="utf-8")
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

__all__ = ["VisitMeta", "ProcessResult", "process_note", "structure_note", "extract", "build_record", "load_config"]


class UnsafeTextError(ValueError):
    """Raised when a note still contains patient identifiers. Nothing is sent."""


class ConversationError(ValueError):
    """Raised when the input looks like a recorded conversation. Nothing is sent."""

    MESSAGE = (
        "Esto parece una conversación, no tu dictado. Dicta tu resumen después de la visita. "
        "No grabes la conversación con el profesional sanitario."
    )


@dataclass
class ProcessResult:
    record: VisitRecord
    anon: AnonResult
    sent_text: str  # exactly what went to the model, for audit and the leak test


def build_user_message(text: str, meta: VisitMeta) -> str:
    fecha = dt.date.fromisoformat(meta.fecha)
    return (
        f"Fecha de la visita: {meta.fecha} ({DIAS[fecha.weekday()]})\n"
        f"Interlocutor: {meta.interlocutor_rol}\n\n"
        f"<nota_kam>\n{text.strip()}\n</nota_kam>"
    )


def extract(text: str, meta: VisitMeta, llm_cfg: dict | None = None) -> tuple[VisitExtraction, str]:
    """Send an already anonymised note to the LLM. Refuses if hard identifiers remain."""
    hits = find_identifiers(text)
    if hits:
        found = ", ".join(label for label, _ in hits)
        raise UnsafeTextError(f"La nota contiene identificadores de paciente ({found}). No se ha enviado nada.")
    user = build_user_message(text, meta)
    return call_llm(SYSTEM_PROMPT, user, llm_cfg or load_config()["llm"]), user


def process_note(raw_text: str, meta: VisitMeta, llm_cfg: dict | None = None) -> ProcessResult:
    is_conv, reasons = looks_like_conversation(raw_text)
    if is_conv:
        raise ConversationError(f"{ConversationError.MESSAGE} ({', '.join(reasons)})")
    anon = anonymize(raw_text, meta.interlocutor_rol)
    ext, sent = extract(anon.text, meta, llm_cfg)
    return ProcessResult(record=build_record(anon.text, meta, ext, anon), anon=anon, sent_text=sent)


def structure_note(raw_text: str, meta: VisitMeta, llm_cfg: dict | None = None) -> VisitRecord:
    return process_note(raw_text, meta, llm_cfg).record
