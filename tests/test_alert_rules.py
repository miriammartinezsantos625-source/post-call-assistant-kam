"""Rule-based safety net. NB: rules were written looking at these 20 notes, so this is not an unbiased estimate."""
import csv

import pytest

from src.alert_rules import detect
from src.anonymize import anonymize
from src.config import ROOT

ROWS = list(csv.DictReader(open(ROOT / "data/demo/notas_sinteticas.csv", encoding="utf-8")))
COLS = {
    "posible_efecto_adverso": "esperado_efecto_adverso",
    "pregunta_fuera_ficha": "esperado_fuera_ficha",
    "solicitud_informacion_medica": "esperado_info_medica",
}


@pytest.mark.parametrize("row", ROWS, ids=[r["nota_id"] for r in ROWS])
def test_rules_match_expected(row):
    got = detect(anonymize(row["texto"], row["interlocutor_rol"]).text)
    for name, col in COLS.items():
        assert got[name]["detectado"] == (row[col] == "true"), name


@pytest.mark.parametrize("text", [
    "Me dice que una paciente se quedó embarazada durante el tratamiento.",
    "Uno de sus chicos tiene tics desde que empezó la medicación.",
    "Comenta un posible efecto secundario, sin más detalle.",
    "Un paciente dejó de funcionarle tras el cambio de presentación.",
])
def test_ae_extra_positives(text):
    assert detect(text)["posible_efecto_adverso"]["detectado"]


def test_fragment_is_a_sentence_of_the_note():
    text = "Hablamos de la guía. Comenta que un paciente tuvo mareos tras empezar. Vuelvo el jueves."
    assert detect(text)["posible_efecto_adverso"]["fragmento"] == "Comenta que un paciente tuvo mareos tras empezar."
