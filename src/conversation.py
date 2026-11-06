"""Rule 0: the app processes the KAM's own dictation, never a recorded conversation.

A post-visit dictation is a first-person narrative about the professional in the
third person ("me pregunta", "le digo"). A conversation has turns, direct address
("usted", "tendríais") and conversational fillers ("vale", "perfecto").
This check runs locally, before anything is sent to the model. The LLM's
`parece_conversacion` flag is a second layer.
"""
from __future__ import annotations

import re

_I = re.IGNORECASE
DIALOGUE_TURN = re.compile(r"(?:^|\s)[—–-]\s*(?=[¿¡A-ZÁÉÍÓÚÑa-záéíóúñ])")
SECOND_PERSON = re.compile(
    r"\b(usted|ustedes|tú|vosotr[oa]s|os|contigo|\w+(?:áis|éis|íais))\b", _I
)
FILLERS = re.compile(r"(?:^|[.?!¿¡,—–-]\s*)(vale|perfecto|claro|mira|oye|bueno|pues|venga|genial|sí|ajá)\b", _I)
DICTATION = re.compile(
    r"\bme (dice|dijo|pregunta|preguntó|cuenta|contó|comenta|comentó|pide|pidió|explica)\b|"
    r"\ble (digo|dije|explico|expliqué|propongo|paso|dejo)\b|\bdice que\b|\bcomenta que\b|"
    r"\bobjetivo\b|\bsiguiente paso\b|\bvisita\b|\bquedamos en\b",
    _I,
)
THRESHOLD = 3


def conversation_score(text: str) -> tuple[int, list[str]]:
    turns = len(DIALOGUE_TURN.findall(text))
    second = len(SECOND_PERSON.findall(text))
    fillers = len(FILLERS.findall(text))
    questions = text.count("?")
    dictation = len(DICTATION.findall(text))
    score = 2 * min(turns, 3) + min(second, 3) + min(fillers, 3) + max(0, min(questions, 4) - 1) - dictation
    reasons = []
    if turns:
        reasons.append(f"{turns} cambios de turno")
    if second:
        reasons.append(f"{second} expresiones dirigidas a otra persona")
    if fillers:
        reasons.append(f"{fillers} muletillas de conversación")
    if questions > 1:
        reasons.append(f"{questions} preguntas directas")
    return score, reasons


def looks_like_conversation(text: str) -> tuple[bool, list[str]]:
    score, reasons = conversation_score(text)
    return score >= THRESHOLD, reasons
