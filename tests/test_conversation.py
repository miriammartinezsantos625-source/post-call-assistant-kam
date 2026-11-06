"""Rule 0: recorded conversations are rejected before anything is sent."""
import csv

import pytest

from src.config import ROOT, VisitMeta
from src.conversation import looks_like_conversation
from src.structure import ConversationError, process_note

ROWS = list(csv.DictReader(open(ROOT / "data/demo/notas_sinteticas.csv", encoding="utf-8")))


@pytest.mark.parametrize("row", ROWS, ids=[r["nota_id"] for r in ROWS])
def test_synthetic_notes(row):
    assert looks_like_conversation(row["texto"])[0] == (row["esperado_conversacion"] == "true")


@pytest.mark.parametrize("text", [
    # as Whisper would transcribe it: no dashes, no speaker labels
    "¿Y para cuándo tendríais el material? Pues calculo que en dos semanas. Vale, y lo de la sesión, ¿lo vemos con el jefe? Sí, mejor con él. Perfecto, te escribo.",
    "Buenos días, ¿usted ha visto los datos nuevos? Sí, claro, me los pasó mi residente. Vale, pues si quiere se los resumo. Venga, genial.",
])
def test_transcribed_conversations(text):
    assert looks_like_conversation(text)[0]


def test_conversation_never_reaches_the_model():
    meta = VisitMeta("2", "psiquiatra adultos", "2026-11-06")
    # provider "none" would raise KeyError if the LLM were ever called
    with pytest.raises(ConversationError):
        process_note(ROWS[-1]["texto"], meta, llm_cfg={"provider": "none"})
