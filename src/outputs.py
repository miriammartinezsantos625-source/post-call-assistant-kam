"""Outputs generated after the KAM approves a record. Nothing is ever sent:
these are files and drafts the KAM downloads or copies.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json

from schema.visit_record import VisitRecord

# CRM-style field names (generic, not tied to any vendor).
CRM_FIELDS = [
    "Call_ID", "Call_Date", "Account_ID", "Account_Segment", "Contact_Role", "Call_Channel",
    "Call_Objective", "Objective_SMART_Gaps", "Objective_Outcome", "Topics_Discussed", "Needs_Identified",
    "Objections", "Materials_Requested", "Next_Step", "Next_Step_Owner", "Follow_Up_Date",
    "Receptivity_1_5", "Cross_Functional_Requests", "AE_Flag", "AE_Reported_To_PV", "Off_Label_Question_Flag",
    "Medical_Info_Request_Flag", "Referred_To_Medical", "Call_Notes",
]
SEP = "; "


def crm_row(rec: VisitRecord) -> dict:
    a = rec.alertas
    medical = a.pregunta_fuera_ficha.detectado or a.solicitud_informacion_medica.detectado
    return {
        "Call_ID": rec.visita_id,
        "Call_Date": rec.fecha,
        "Account_ID": rec.cuenta_id,
        "Account_Segment": rec.segmento or "",
        "Contact_Role": rec.interlocutor_rol,
        "Call_Channel": rec.canal or "",
        "Call_Objective": rec.objetivo_visita or "",
        "Objective_SMART_Gaps": SEP.join(rec.objetivo_smart.que_falta) if rec.objetivo_smart else "",
        "Objective_Outcome": rec.objetivo_cumplido or "",
        "Topics_Discussed": SEP.join(rec.temas_tratados),
        "Needs_Identified": SEP.join(rec.necesidades_detectadas),
        "Objections": SEP.join(f"{o.tipo}: {o.texto}" for o in rec.objeciones),
        "Materials_Requested": SEP.join(rec.materiales_solicitados),
        "Next_Step": rec.siguiente_paso or "",
        "Next_Step_Owner": rec.responsable_siguiente_paso or "",
        "Follow_Up_Date": rec.fecha_seguimiento or "",
        "Receptivity_1_5": rec.receptividad.valor_1_5 or "",
        "Cross_Functional_Requests": SEP.join(f"{c.area}: {c.peticion}" for c in rec.colaboracion_transversal),
        "AE_Flag": a.posible_efecto_adverso.detectado,
        "AE_Reported_To_PV": a.posible_efecto_adverso.confirmado_por_kam,
        "Off_Label_Question_Flag": a.pregunta_fuera_ficha.detectado,
        "Medical_Info_Request_Flag": a.solicitud_informacion_medica.detectado,
        "Referred_To_Medical": medical and (a.pregunta_fuera_ficha.confirmado_por_kam or a.solicitud_informacion_medica.confirmado_por_kam),
        "Call_Notes": rec.resumen_crm,
    }


def crm_csv(recs: list[VisitRecord]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CRM_FIELDS)
    w.writeheader()
    for r in recs:
        w.writerow(crm_row(r))
    return buf.getvalue()


def crm_json(rec: VisitRecord) -> str:
    return json.dumps(crm_row(rec), ensure_ascii=False, indent=2)


def _ics_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545: lines longer than 75 octets are folded."""
    out, cur = [], ""
    for ch in line:
        if len((cur + ch).encode()) > 74:
            out.append(cur)
            cur = " " + ch
        else:
            cur += ch
    return "\r\n".join(out + [cur])


def followup_ics(rec: VisitRecord, centro: str | None = None) -> str | None:
    """All-day reminder on the follow-up date, with an alarm the day before. None if no date."""
    if not rec.fecha_seguimiento:
        return None
    day = dt.date.fromisoformat(rec.fecha_seguimiento)
    where = f"cuenta {rec.cuenta_id}" + (f" ({centro})" if centro else "")
    desc = [f"Siguiente paso: {rec.siguiente_paso or '—'}",
            f"Responsable: {rec.responsable_siguiente_paso or '—'}",
            f"Visita del {rec.fecha} a {rec.interlocutor_rol}."]
    if rec.materiales_solicitados:
        desc.append("Materiales pedidos: " + SEP.join(rec.materiales_solicitados))
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Post-Call Assistant//ES", "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:{rec.visita_id}@post-call-assistant",
        f"DTSTAMP:{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%SZ}",
        f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
        f"DTEND;VALUE=DATE:{day + dt.timedelta(days=1):%Y%m%d}",
        f"SUMMARY:{_ics_escape('Seguimiento ' + where + ': ' + (rec.siguiente_paso or 'siguiente paso'))}",
        f"DESCRIPTION:{_ics_escape(chr(10).join(desc))}",
        "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Seguimiento de visita", "TRIGGER:-P1D", "END:VALARM",
        "END:VEVENT", "END:VCALENDAR",
    ]
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def followup_email(rec: VisitRecord) -> str:
    """Neutral, non-promotional draft to the professional. Never sent by the app.

    It never mentions adverse events or answers clinical questions: those go
    through Pharmacovigilance and Medical Information.
    """
    a = rec.alertas
    body = ["Estimado/a doctor/a:", "",
            f"Muchas gracias por su tiempo en nuestra reunión del {dt.date.fromisoformat(rec.fecha):%d/%m/%Y}."]
    if rec.materiales_solicitados:
        body += ["", "Tal como me pidió, le hago llegar:"] + [f"  - {m}" for m in rec.materiales_solicitados]
    if a.pregunta_fuera_ficha.detectado or a.solicitud_informacion_medica.detectado:
        body += ["", "He trasladado su consulta al departamento de Información Médica, que se pondrá en contacto "
                     "con usted directamente."]
    if rec.responsable_siguiente_paso == "KAM" and rec.fecha_seguimiento:
        # The date only: the model's wording of the next step is not copied into a message to the HCP.
        body += ["", f"Como acordamos, retomaremos el contacto el {dt.date.fromisoformat(rec.fecha_seguimiento):%d/%m/%Y}."]
    body += ["", "Quedo a su disposición para cualquier cuestión.", "", "Un cordial saludo,", "[Tu nombre]",
             "Key Account Manager · Neurociencias"]
    return "\n".join(body)
