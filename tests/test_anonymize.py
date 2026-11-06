"""Anonymisation: zero leaks on the synthetic set, no over-redaction, extra cases."""
import csv

import pytest

from src.anonymize import anonymize, find_identifiers
from src.config import ROOT

ROWS = list(csv.DictReader(open(ROOT / "data/demo/notas_sinteticas.csv", encoding="utf-8")))


@pytest.mark.parametrize("row", ROWS, ids=[r["nota_id"] for r in ROWS])
def test_no_identifier_survives(row):
    out = anonymize(row["texto"], row["interlocutor_rol"]).text
    secrets = [s for s in (row["identificadores_paciente"] + "|" + row["nombres_medico"]).split("|") if s]
    for s in secrets:
        assert s.lower() not in out.lower(), f"leak: {s}"
    assert find_identifiers(out) == []


@pytest.mark.parametrize("row", [r for r in ROWS if not r["identificadores_paciente"] and not r["nombres_medico"]],
                         ids=lambda r: r["nota_id"])
def test_clean_notes_are_untouched(row):
    assert anonymize(row["texto"], row["interlocutor_rol"]).text == row["texto"]


@pytest.mark.parametrize("text,secret,tag", [
    ("La paciente, María Pérez, con DNI 12345678Z, tuvo náuseas.", "12345678Z", "[DNI]"),
    ("La paciente, María Pérez, con DNI 12345678Z, tuvo náuseas.", "María Pérez", "[PACIENTE]"),
    ("Escribe a la madre a madre.ejemplo@correo.es si hay novedades.", "madre.ejemplo@correo.es", "[EMAIL]"),
    ("El niño, nacido el 03/04/2017, ingresó el lunes.", "03/04/2017", "[FECHA_NAC]"),
    ("Paciente Marta tuvo cefalea tras la primera toma.", "Marta", "[PACIENTE]"),
    ("Historia clínica 99887766 con varios ingresos.", "99887766", "[NHC]"),
    ("Me pasó el caso de Javier M., de 9 años.", "9 años", "[EDAD]"),
    ("Hablé con la doctora Elena Soler sobre el circuito.", "Elena Soler", "[neuropediatra]"),
    ("Llámame al +34 699 11 22 33 mañana.", "699 11 22 33", "[TELÉFONO]"),
])
def test_extra_cases(text, secret, tag):
    out = anonymize(text, "neuropediatra").text
    assert secret not in out and tag in out


@pytest.mark.parametrize("text", [
    "Me pregunta si hay datos en niños menores de seis años.",
    "Lo traslado a Medical y a Market Access.",
    "Quedamos el 15 de diciembre en el Hospital Demo Norte.",
    "La lista de espera es de cuatro meses.",
])
def test_no_over_redaction(text):
    assert anonymize(text).text == text


def test_report_never_needed_to_rebuild_text():
    res = anonymize("Me cuenta que Lucía Ferrer, de 11 años, NHC 4482913, fue a urgencias.", "psiquiatra infantil")
    assert {r.tipo for r in res.replacements} == {"Nombre de paciente", "Edad de paciente", "Historia clínica"}
