"""One-off: apply the KAM's review edits to the 19 demo records (data/demo/historial_demo.jsonl).

The records were produced by the local model on the synthetic notes. Before using them as the public
demo history they get the corrections a KAM would make on approval: only what the note says, neutral
compliance wording ("posible efecto adverso"), no invented needs, no patient details in summaries.
Usage: .venv/bin/python -m scripts.clean_demo_history
"""
from __future__ import annotations

import csv

from schema.visit_record import VisitRecord
from src.config import ROOT

PATH = ROOT / "data/demo/historial_demo.jsonl"
NOTES = {r["nota_id"]: r for r in csv.DictReader(open(ROOT / "data/demo/notas_sinteticas.csv", encoding="utf-8"))}

EDITS: dict[str, dict] = {
    "N02": dict(
        temas_tratados=["posible efecto adverso comunicado (insomnio, pérdida de apetito)", "circuitos de derivación con primaria"],
        necesidades_detectadas=[],
        resumen_crm="Visita a la jefa de servicio. Se registra posible efecto adverso en un paciente (insomnio y pérdida de "
                    "apetito tras iniciar el tratamiento) para su notificación a Farmacovigilancia. Se acuerda hablar de "
                    "circuitos de derivación con primaria el mes que viene.",
    ),
    "N05": dict(materiales_solicitados=[]),
    "N09": dict(
        temas_tratados=["posible efecto adverso comunicado (taquicardia)", "programa de transición a adultos"],
        necesidades_detectadas=[],
        siguiente_paso="Volver a verse el 2 de diciembre",
        alertas_off=["solicitud_informacion_medica"],
        resumen_crm="Visita a la psiquiatra infantil. Se registra posible efecto adverso (taquicardia tras iniciar el "
                    "tratamiento) para su notificación a Farmacovigilancia. Se comenta el programa de transición a adultos. "
                    "Nueva visita el 2 de diciembre.",
    ),
    "N10": dict(
        temas_tratados=["posible falta de eficacia tras el cambio de presentación", "posible efecto adverso comunicado (mareos)",
                        "nuevo material de formación (pospuesto)"],
        necesidades_detectadas=[],
        siguiente_paso="Volver el jueves para presentar el material de formación",
        resumen_crm="Psiquiatra de adultos comenta que varios pacientes no responden igual tras el cambio de presentación y "
                    "que uno refiere mareos: se registra posible efecto adverso para su notificación a Farmacovigilancia. "
                    "La presentación del material de formación se pospone; seguimiento el jueves.",
    ),
    "N11": dict(
        temas_tratados=["datos de seguimiento a largo plazo", "pregunta sobre aumento de dosis en pacientes no respondedores"],
        necesidades_detectadas=[],
        siguiente_paso="Medical contacta al profesional en una semana",
    ),
    "N13": dict(siguiente_paso="Volver a verse en un mes"),
    "N14": dict(resumen_crm="Visita a la psiquiatra de adultos para confirmar su participación como ponente en la reunión "
                            "regional de marzo. La profesional acepta y se muestra muy receptiva. Marketing enviará la "
                            "invitación formal esta semana."),
    "N15": dict(
        objeciones=[{"tipo": "organizativa", "texto": "faltan neuropediatras y las listas de espera son largas"}],
        necesidades_detectadas=["reducir los tiempos de espera para cita"],
        resumen_crm="Visita al neuropediatra. Objeción organizativa: faltan neuropediatras y las listas de espera son largas. "
                    "La KAM propone hablar con dirección sobre un circuito de enfermería y preparará una propuesta en tres "
                    "semanas.",
    ),
}


def note_id(rec: VisitRecord) -> str:
    return next(k for k, n in NOTES.items()
                if n["cuenta_id"] == rec.cuenta_id and n["fecha"] == rec.fecha and n["interlocutor_rol"] == rec.interlocutor_rol)


def main() -> None:
    out = []
    for line in PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = VisitRecord.model_validate_json(line)
        nid = note_id(rec)
        data = rec.model_dump()
        edit = dict(EDITS.get(nid, {}))
        for name in edit.pop("alertas_off", []):
            data["alertas"][name] = {"detectado": False, "fragmento": "", "fuente": [], "otros_fragmentos": [],
                                     "confirmado_por_kam": False}
        data.update(edit)
        data["avisos_validacion"] = []
        out.append(VisitRecord.model_validate(data).model_dump_json())
        print(nid, "edited" if nid in EDITS else "kept")
    PATH.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
