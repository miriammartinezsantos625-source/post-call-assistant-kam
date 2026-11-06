"""Post-Call Assistant KAM — Neurociencias.

AI drafts, the KAM decides. Nothing is saved or exported without explicit approval,
and the app never sends anything on its own.
"""
from __future__ import annotations

import csv
import datetime as dt
import time

import pandas as pd
import streamlit as st

from schema.visit_record import VisitRecord
from src import ui
from src.config import ROOT, VisitMeta, is_demo, load_config
from src.dates import has_deadline
from src.llm import LLMOutputError
from src.outputs import crm_csv, crm_json, followup_email, followup_ics
from src.storage import (
    Metrics, clear_demo, list_visits, mark_followup_done, next_visit_brief, record_of, save_approved, visitas_csv,
)
from src.structure import ConversationError, UnsafeTextError, process_note
from src.validate import ALERT_MESSAGES, CORE_FIELDS, RESUMEN_MAX, summary_warnings

CFG = load_config()
DEMO = is_demo()
MODEL = f'{CFG["llm"]["ollama"]["model"]} (fichas pregeneradas)' if DEMO else CFG["llm"][CFG["llm"]["provider"]]["model"]
ALERT_UI = {
    "posible_efecto_adverso": ("Farmacovigilancia", "Posible efecto adverso", "He notificado a Farmacovigilancia"),
    "pregunta_fuera_ficha": ("Medical", "Pregunta que puede estar fuera de ficha técnica", "He derivado la pregunta a Medical / Información Médica"),
    "solicitud_informacion_medica": ("Medical", "Solicitud de información médica", "He derivado la solicitud a Medical / Información Médica"),
}
NONE = "—"
MODES = {"Escribir": ":material/edit_note:", "Dictar": ":material/mic:", "Subir audio": ":material/upload_file:"}

st.set_page_config(page_title="Post-Call Assistant KAM", page_icon=str(ROOT / "assets/logo_icon.svg"), layout="wide")
st.logo(str(ROOT / "assets/logo.svg"), size="large", icon_image=str(ROOT / "assets/logo_icon.svg"))
ui.inject_css()


def seed_demo_history() -> None:
    for line in (ROOT / "data/demo/historial_demo.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            save_approved(VisitRecord.model_validate_json(line), demo=True)


if DEMO and "demo_seeded" not in st.session_state:
    if not list_visits():
        seed_demo_history()
    st.session_state.demo_seeded = True


# ------------------------------------------------------------------ data
@st.cache_data
def cuentas() -> pd.DataFrame:
    return pd.read_csv(ROOT / CFG["data"]["cuentas_csv"], dtype=str)


@st.cache_data
def demo_notes() -> list[dict]:
    rows = list(csv.DictReader(open(ROOT / "data/demo/notas_sinteticas.csv", encoding="utf-8")))
    return [r for r in rows if r["esperado_conversacion"] != "true"]


def cuenta_row(cid: str) -> pd.Series:
    return cuentas().set_index("cuenta_id").loc[cid]


def cuenta_label(cid: str) -> str:
    r = cuenta_row(cid)
    return f"{cid} · {r['centro']}"


def fmt(d: str | None) -> str:
    return dt.date.fromisoformat(d).strftime("%d/%m/%Y") if d else "—"


def idx(options: list, value) -> int:
    """Index of value in options, falling back to the empty choice for unexpected model output."""
    return options.index(value) if value in options else 0


def lines(s: str) -> list[str]:
    return [x.strip(" -•\t") for x in s.splitlines() if x.strip(" -•\t")]


def reset_visit() -> None:
    for k in ("stage", "result", "t0", "t_proceso", "approved", "metrics"):
        st.session_state.pop(k, None)


# ------------------------------------------------------------------ 1 · new visit
def page_new_visit() -> None:
    stage = st.session_state.get("stage", "input")
    if stage == "review":
        return review_stage()
    if stage == "done":
        return outputs_stage()

    ui.stepper(0)
    ui.hero(
        "Post-call intelligence · Neurociencias",
        "Del dictado a la <em>ficha CRM</em>,<br>en menos de dos minutos",
        "Dicta tu resumen al salir de la consulta. La IA estructura la visita, detecta alertas de compliance y "
        "prepara el seguimiento. <b>Tú revisas y decides.</b>",
        ["Procesado 100 % en local", "Anonimización previa a la IA", "Alertas de Farmacovigilancia y Medical",
         "Aprobación obligatoria"],
    )

    st.session_state.setdefault("nv_fecha", dt.date.today())
    left, right = st.columns([1.65, 1], gap="large")
    df = cuentas()
    with left:
        ui.section("01", "Contexto de la visita")
        c1, c2 = st.columns(2)
        cid = c1.selectbox("Cuenta", df["cuenta_id"].tolist(), format_func=cuenta_label, key="nv_cuenta")
        rol = c2.selectbox("Interlocutor (rol)", CFG["roles"], key="nv_rol")
        c3, c4 = st.columns(2)
        fecha = c3.date_input("Fecha de la visita", format="DD/MM/YYYY", key="nv_fecha")
        canal = c4.selectbox("Canal", ["presencial", "remoto", "telefónico"], key="nv_canal")

        ui.section("02", "Tu resumen de la visita")
        st.markdown('<p class="muted" style="margin:-.2rem 0 .7rem">Dicta tu resumen <b>después</b> de la visita, a solas. '
                    '<b>No grabes la conversación</b> con el profesional sanitario.</p>', unsafe_allow_html=True)
        modes = ["Escribir"] if DEMO else list(MODES)
        modo = st.segmented_control("Formato", modes, default="Escribir", key="nv_modo",
                                    format_func=lambda m: f"{MODES[m]} {m}", label_visibility="collapsed")
        if DEMO:
            st.caption("Demo pública: elige una nota sintética. El dictado y la IA funcionan en local (Whisper + Ollama).")
        audio = upload = None
        if modo == "Dictar":
            audio = st.audio_input("Graba tu resumen (1–2 minutos)")
        elif modo == "Subir audio":
            upload = st.file_uploader("Archivo de audio (.m4a, .mp3, .wav)", type=["m4a", "mp3", "wav"])
        else:
            notes = demo_notes()

            def load_example():
                n = next((x for x in notes if x["nota_id"] == st.session_state.nv_ejemplo), None)
                if n:
                    st.session_state.update(nv_texto=n["texto"], nv_cuenta=n["cuenta_id"], nv_rol=n["interlocutor_rol"],
                                            nv_canal=n["canal"], nv_fecha=dt.date.fromisoformat(n["fecha"]))

            st.selectbox("Nota sintética de ejemplo (demo)", [""] + [n["nota_id"] for n in notes], key="nv_ejemplo",
                         on_change=load_example,
                         format_func=lambda i: "Elegir una nota de ejemplo…" if not i
                         else f"{i} · {next(n['categoria'] for n in notes if n['nota_id'] == i)}")
            st.text_area("Resumen", height=170, key="nv_texto", label_visibility="collapsed",
                         placeholder="Visita a la jefa de servicio de la cuenta 4. Objetivo: … Siguiente paso: …")

        go = st.button("Generar ficha", type="primary", icon=":material/auto_awesome:")

    with right:
        r = cuenta_row(cid)
        b = next_visit_brief(cid)
        last = None
        if b.ultima:
            last = f"<b>{fmt(b.ultima.fecha)}</b> · {ui.esc(b.ultima.interlocutor_rol)}<br>{ui.esc(b.ultima.resumen_crm)}"
        ui.account_card(cid, r["centro"], r["tipo_centro"], r["provincia"], r["segmento"], last, len(b.compromisos))
        st.markdown(
            '<div class="howto">'
            '<span class="eyebrow">Cómo funciona</span><br>'
            '1 · Transcripción local (Whisper)<br>2 · Bloqueo de conversaciones grabadas<br>'
            '3 · Anonimización: pacientes → [PACIENTE], médicos → rol<br>4 · Ficha estructurada con IA local + reglas de compliance<br>'
            '5 · Revisión y aprobación de la KAM</div>',
            unsafe_allow_html=True,
        )

    if not go:
        return
    if audio is None and upload is None and not st.session_state.get("nv_texto", "").strip():
        st.error("Escribe, dicta o sube una nota primero.")
        return
    meta = VisitMeta(cid, rol, fecha.isoformat(), cuenta_row(cid)["segmento"], canal)
    t0 = time.time()
    try:
        with st.status("Procesando en este equipo…", expanded=True) as status:
            if audio is not None or upload is not None:
                from src.transcribe import transcribe_bytes

                st.write("Transcribiendo el audio con Whisper (local)…")
                f = audio if audio is not None else upload
                suffix = "." + (f.name.rsplit(".", 1)[-1] if upload is not None else "wav")
                texto = transcribe_bytes(f.getvalue(), suffix=suffix).text  # temp file deleted inside
                st.write(f"Transcripción: _{texto}_")
            else:
                texto = st.session_state.nv_texto.strip()
            st.write("Comprobando que es un dictado · anonimizando · estructurando con la IA local…")
            result = process_note(texto, meta)
            status.update(label="Propuesta lista para tu revisión", state="complete")
    except (ConversationError, UnsafeTextError) as e:
        st.error(str(e), icon=":material/block:")
        return
    except LLMOutputError as e:
        st.error(f"No se ha podido generar la ficha: {e}")
        return
    except Exception as e:  # noqa: BLE001 - show any failure to the user
        st.error(f"No se ha podido generar la ficha: {e}")
        return
    st.session_state.update(stage="review", result=result, t0=t0, t_proceso=time.time() - t0)
    st.rerun()


# ------------------------------------------------------------------ 2 · review
def review_stage() -> None:
    res = st.session_state.result
    rec: VisitRecord = res.record
    k = rec.visita_id[:8]
    ui.stepper(3)
    ui.hero(
        "Paso 04 · Revisión de la KAM",
        "Revisa, corrige y <em>aprueba</em>",
        "La IA propone; tú decides. Nada se guarda ni se exporta sin tu aprobación.",
        [f"Cuenta {cuenta_label(rec.cuenta_id)}", rec.interlocutor_rol, fmt(rec.fecha), rec.canal or "—",
         f"Propuesta generada en {st.session_state.t_proceso:.0f} s"],
    )
    faltan = set(rec.campos_faltantes)

    def label(text: str, field: str) -> str:
        return f"{text}  ·  :gray[**falta**]" if field in faltan else text

    left, right = st.columns([1.7, 1], gap="large")
    with left:
        ui.section("01", "Objetivo y resultado")
        objetivo = st.text_input(label("Objetivo de la visita", "objetivo_visita"), rec.objetivo_visita or "", key=f"{k}_obj")
        if objetivo:
            sm = rec.objetivo_smart
            plazo = has_deadline(objetivo)
            esp, med = (sm.especifico, sm.medible) if sm else (False, False)
            gaps = [q for q in (sm.que_falta if sm else []) if "plazo" not in q.lower()] + ([] if plazo else ["no incluye un plazo"])
            st.markdown(
                '<div style="margin:-.3rem 0 .6rem"><span class="mono muted" style="font-size:.66rem;letter-spacing:.14em">SMART&nbsp;&nbsp;</span>'
                + ui.badge("específico", "ok" if esp else "no") + ui.badge("medible", "ok" if med else "no")
                + ui.badge("con plazo", "ok" if plazo else "no")
                + (f'<div class="muted" style="margin-top:.35rem">Le falta: {ui.esc("; ".join(gaps))}</div>' if gaps else "")
                + "</div>",
                unsafe_allow_html=True,
            )
        c1, c2 = st.columns(2)
        opts = [NONE, "si", "parcial", "no"]
        cumplido = c1.selectbox(label("¿Objetivo cumplido?", "objetivo_cumplido"), opts,
                                index=idx(opts, rec.objetivo_cumplido), key=f"{k}_cump")
        vopts = [NONE, 1, 2, 3, 4, 5]
        recep = c2.selectbox(label("Receptividad (1–5)", "receptividad"), vopts,
                             index=idx(vopts, rec.receptividad.valor_1_5), key=f"{k}_rec")
        motivo = st.text_input("En qué se basa la receptividad", rec.receptividad.motivo or "", key=f"{k}_mot")

        ui.section("02", "Contenido de la visita")
        c1, c2 = st.columns(2)
        temas = c1.text_area(label("Temas tratados", "temas_tratados"), "\n".join(rec.temas_tratados), key=f"{k}_temas", height=110)
        necesidades = c2.text_area("Necesidades detectadas", "\n".join(rec.necesidades_detectadas), key=f"{k}_nec", height=110)
        materiales = st.text_area("Materiales solicitados", "\n".join(rec.materiales_solicitados), key=f"{k}_mat", height=70)
        obj_df = st.data_editor(
            pd.DataFrame([o.model_dump() for o in rec.objeciones], columns=["tipo", "texto"]),
            num_rows="dynamic", width="stretch", key=f"{k}_objeciones",
            column_config={"tipo": st.column_config.SelectboxColumn("Objeción · tipo", options=["cientifica", "acceso", "proceso", "organizativa", "otra"], width="small"),
                           "texto": st.column_config.TextColumn("Objeción", width="large")},
        )

        ui.section("03", "Siguiente paso")
        siguiente = st.text_input(label("Siguiente paso", "siguiente_paso"), rec.siguiente_paso or "", key=f"{k}_sig")
        c1, c2 = st.columns(2)
        fs = dt.date.fromisoformat(rec.fecha_seguimiento) if rec.fecha_seguimiento else None
        fecha_seg = c1.date_input(label("Fecha de seguimiento", "fecha_seguimiento"), fs, format="DD/MM/YYYY", key=f"{k}_fseg",
                                  help=f"En la nota: «{rec.fecha_seguimiento_expresion}»" if rec.fecha_seguimiento_expresion else None)
        ropts = [NONE, "KAM", "Medical", "Market Access", "Marketing"]
        resp = c2.selectbox(label("Responsable", "responsable_siguiente_paso"), ropts,
                            index=idx(ropts, rec.responsable_siguiente_paso), key=f"{k}_resp")
        col_df = st.data_editor(
            pd.DataFrame([c.model_dump() for c in rec.colaboracion_transversal], columns=["area", "peticion"]),
            num_rows="dynamic", width="stretch", key=f"{k}_colab",
            column_config={"area": st.column_config.SelectboxColumn("Colaboración · área", options=["Medical", "Market Access", "Marketing"], width="small"),
                           "peticion": st.column_config.TextColumn("Petición", width="large")},
        )

        ui.section("04", "Resumen para el CRM")
        # No max_chars: Streamlit would silently cut a longer AI summary mid-sentence.
        resumen = st.text_area("Resumen", rec.resumen_crm, height=120, key=f"{k}_res", label_visibility="collapsed")
        st.caption(f"{len(resumen)} / {RESUMEN_MAX} caracteres")
        for w in summary_warnings(resumen, None if cumplido == NONE else cumplido):
            ui.note(w)

    with right:
        st.markdown('<span class="decision-anchor"></span>', unsafe_allow_html=True)
        ui.section("◆", "Panel de decisión")
        detected = [n for n, a in rec.alertas.model_dump().items() if a["detectado"]]
        confirmations = {}
        if detected:
            for name in detected:
                al = getattr(rec.alertas, name)
                tag, title, confirm = ALERT_UI[name]
                ui.alert_card(f"Alerta de compliance · {tag}", title, [al.fragmento] + list(al.otros_fragmentos),
                              ALERT_MESSAGES[name], f"Detectado por {' + '.join(al.fuente)}. La app solo avisa: actúas tú.")
                st.text_input("Fragmento que se guardará", al.fragmento, key=f"{k}_frag_{name}",
                              help="Puedes corregir errores de transcripción.")
                confirmations[name] = st.checkbox(confirm, key=f"{k}_ok_{name}")
        else:
            st.markdown('<div class="ok-panel"><b>Sin alertas de compliance.</b><br>Ni la IA ni las reglas han detectado '
                        'posibles efectos adversos ni preguntas para Medical.</div>', unsafe_allow_html=True)

        for a in rec.avisos_validacion:
            if not a.startswith("El resumen CRM") and not a.startswith("Se han anonimizado"):
                ui.note(a)

        n_sust = len(res.anon.replacements)
        with st.expander(f"Privacidad · {n_sust} dato{'s' if n_sust != 1 else ''} sustituido{'s' if n_sust != 1 else ''} antes de la IA",
                         icon=":material/shield:"):
            if res.anon.replacements:
                st.markdown("\n".join(f"- {r.tipo} → `{r.sustituto}`" for r in res.anon.replacements))
            st.caption("Texto exacto que ha procesado el modelo:")
            st.code(res.anon.text, language=None, wrap_lines=True)

        st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
        missing = [f"confirma «{ALERT_UI[n][1]}»" for n, ok in confirmations.items() if not ok]
        if len(resumen) > RESUMEN_MAX:
            missing.append(f"acorta el resumen a {RESUMEN_MAX} caracteres")
        approve = st.button("Aprobar y guardar", type="primary", icon=":material/verified:", disabled=bool(missing), width="stretch")
        if missing:
            st.caption("Para aprobar: " + "; ".join(missing) + ".")
        if st.button("Descartar propuesta", icon=":material/close:", width="stretch"):
            reset_visit()
            st.rerun()

    if not approve:
        return

    def rows(df: pd.DataFrame, a: str, b: str) -> list[dict]:
        return [{a: r[a], b: r[b]} for r in df.to_dict("records") if r.get(a) and r.get(b)]

    alertas = rec.alertas.model_copy(deep=True)
    for name in detected:
        al = getattr(alertas, name)
        al.fragmento = st.session_state[f"{k}_frag_{name}"]
        al.confirmado_por_kam = True
    smart = rec.objetivo_smart.model_copy() if (rec.objetivo_smart and objetivo) else None
    if smart:
        smart.con_plazo = has_deadline(objetivo)
    approved = VisitRecord.model_validate({**rec.model_dump(), **dict(
        objetivo_visita=objetivo or None, objetivo_smart=smart.model_dump() if smart else None,
        objetivo_cumplido=None if cumplido == NONE else cumplido,
        temas_tratados=lines(temas), necesidades_detectadas=lines(necesidades), materiales_solicitados=lines(materiales),
        objeciones=rows(obj_df, "tipo", "texto"), colaboracion_transversal=rows(col_df, "area", "peticion"),
        siguiente_paso=siguiente or None, fecha_seguimiento=fecha_seg.isoformat() if fecha_seg else None,
        responsable_siguiente_paso=None if resp == NONE else resp,
        receptividad={"valor_1_5": None if recep == NONE else recep, "motivo": motivo or None},
        alertas=alertas.model_dump(), resumen_crm=resumen, aprobado=True,
    )})
    compare = ["objetivo_visita", "objetivo_cumplido", "temas_tratados", "necesidades_detectadas", "materiales_solicitados",
               "objeciones", "colaboracion_transversal", "siguiente_paso", "fecha_seguimiento",
               "responsable_siguiente_paso", "receptividad", "resumen_crm"]
    before, after = rec.model_dump(), approved.model_dump()
    approved.campos_faltantes = [
        f for f in CORE_FIELDS if (after["receptividad"]["valor_1_5"] is None if f == "receptividad" else not after[f])
    ]
    m = Metrics(segundos_proceso=round(st.session_state.t_proceso, 1),
                segundos_total=round(time.time() - st.session_state.t0, 1),
                campos_auto=round(1 - len([f for f in rec.campos_faltantes if f in CORE_FIELDS]) / len(CORE_FIELDS), 3),
                campos_editados=sum(before[f] != after[f] for f in compare))
    save_approved(approved, m)
    st.session_state.update(stage="done", approved=approved, metrics=m)
    st.rerun()


# ------------------------------------------------------------------ 3 · outputs
def outputs_stage() -> None:
    rec: VisitRecord = st.session_state.approved
    m: Metrics = st.session_state.metrics
    ui.stepper(4)
    ui.hero("Paso 05 · Salidas", "Ficha <em>aprobada</em> y lista para el CRM",
            "Guardada en el historial local. Descarga lo que necesites: la app no envía nada por su cuenta.")
    ui.kpis([
        ("Nota → ficha aprobada", f"{m.segundos_total:.0f}<small>s</small>", "objetivo: menos de 120 s"),
        ("Propuesta de la IA", f"{m.segundos_proceso:.0f}<small>s</small>", "transcripción + IA local"),
        ("Campos autocompletados", f"{100 * m.campos_auto:.0f}<small>%</small>", "sobre los campos clave"),
        ("Campos editados", f"{m.campos_editados}", "por la KAM antes de aprobar"),
    ], dark_first=True)

    ui.section("01", "Entregables")
    centro = cuenta_row(rec.cuenta_id)["centro"]
    ics = followup_ics(rec, centro)
    c = st.columns(3, gap="medium")
    with c[0]:
        st.markdown('<div class="deliv"><div class="ic">CRM · CSV</div><h4>Registro de visita</h4>'
                    '<p>Campos con nomenclatura CRM, alertas y confirmaciones incluidas.</p></div>', unsafe_allow_html=True)
        st.download_button("Descargar CSV", crm_csv([rec]), f"visita_{rec.fecha}_cuenta{rec.cuenta_id}.csv", "text/csv",
                           icon=":material/table_view:", width="stretch")
    with c[1]:
        st.markdown('<div class="deliv"><div class="ic">CRM · JSON</div><h4>Integración</h4>'
                    '<p>El mismo registro en JSON, listo para una carga por API.</p></div>', unsafe_allow_html=True)
        st.download_button("Descargar JSON", crm_json(rec), f"visita_{rec.fecha}_cuenta{rec.cuenta_id}.json",
                           "application/json", icon=":material/data_object:", width="stretch")
    with c[2]:
        when = fmt(rec.fecha_seguimiento) if rec.fecha_seguimiento else "sin fecha"
        st.markdown(f'<div class="deliv"><div class="ic">Calendario · ICS</div><h4>Seguimiento · {when}</h4>'
                    '<p>Evento de día completo con aviso la víspera.</p></div>', unsafe_allow_html=True)
        if ics:
            st.download_button("Descargar .ics", ics, f"seguimiento_cuenta{rec.cuenta_id}.ics", "text/calendar",
                               icon=":material/event:", width="stretch")
        else:
            st.caption("Añade una fecha de seguimiento para generar el recordatorio.")

    ui.section("02", "Borrador de email de seguimiento")
    st.caption("Para copiar y revisar. No se envía. Nunca incluye efectos adversos ni respuestas clínicas.")
    st.code(followup_email(rec), language=None, wrap_lines=True)

    with st.expander("Ficha aprobada completa (JSON)", icon=":material/description:"):
        st.json(rec.model_dump(exclude={"avisos_validacion"}))
    if st.button("Registrar otra visita", type="primary", icon=":material/add:"):
        reset_visit()
        st.rerun()


# ------------------------------------------------------------------ 4 · history
def page_history() -> None:
    ui.hero("Account intelligence", "Historial y <em>brief</em> de la próxima visita",
            "Cada visita aprobada alimenta el contexto de la cuenta: compromisos, objeciones abiertas y alertas gestionadas, "
            "listos para preparar la siguiente.")
    rows = list_visits()
    with st.sidebar:
        st.markdown('<div class="mono" style="font-size:.62rem;letter-spacing:.18em;color:#8AAFC8;margin:1.2rem 0 .4rem">DATOS DE DEMO</div>',
                    unsafe_allow_html=True)
        if st.button("Cargar 19 visitas sintéticas", icon=":material/dataset:", width="stretch"):
            seed_demo_history()
            st.rerun()
        if st.button("Borrar visitas de demo", icon=":material/delete_sweep:", width="stretch"):
            clear_demo()
            st.rerun()
    if not rows:
        st.info("Todavía no hay visitas aprobadas. Registra una o carga las visitas sintéticas desde la barra lateral.")
        return

    ids = sorted({r["cuenta_id"] for r in rows}, key=int)
    c1, _ = st.columns([1.2, 2])
    cid = c1.selectbox("Cuenta", ids, format_func=lambda i: f"{cuenta_label(i)} · segmento {cuenta_row(i)['segmento']}")
    b = next_visit_brief(cid)
    acc_rows = list_visits(cid)
    n_alerts = sum(r["alerta_ea"] + r["alerta_ff"] + r["alerta_im"] for r in acc_rows)
    overdue = sum(1 for _, o in b.compromisos if o)
    ui.kpis([
        ("Visitas registradas", str(b.n_visitas), f"segmento {cuenta_row(cid)['segmento']}"),
        ("Compromisos abiertos", str(len(b.compromisos)), f"{overdue} vencidos" if overdue else "al día"),
        ("Alertas gestionadas", str(n_alerts), "FV y Medical, confirmadas"),
        ("Última visita", fmt(b.ultima.fecha) if b.ultima else "—", b.ultima.interlocutor_rol if b.ultima else ""),
    ])

    def li(items: list[str]) -> str:
        return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>" if items else '<div class="none">Ninguno.</div>'

    comp = [(f'<span class="over">VENCIDO</span>' if o else "") + f'{ui.esc(r.siguiente_paso)} '
            f'<span class="d">· {ui.esc(r.responsable_siguiente_paso or "—")} · {fmt(r.fecha_seguimiento)}</span>'
            for r, o in b.compromisos]
    obj = [f'{ui.esc(x)} <span class="d">· {t} · {fmt(f)}</span>' for f, t, x in b.objeciones]
    mat = [f'{ui.esc(x)} <span class="d">· {fmt(f)}</span>' for f, x in b.materiales]
    ale = [f'{ui.esc(t)} <span class="d">· {fmt(f)}</span>' for f, t in b.alertas]
    u = b.ultima
    st.markdown(
        f"""<div class="brief"><div class="eyebrow">Brief de la próxima visita</div>
        <h3>{ui.esc(cuenta_row(cid)['centro'])}</h3>
        <div class="summary">{ui.esc(u.resumen_crm) if u else ''}</div>
        <div class="grid">
          <div><h5>Compromisos pendientes</h5>{li(comp)}</div>
          <div><h5>Objeciones abiertas</h5>{li(obj)}</div>
          <div><h5>Materiales pedidos</h5>{li(mat)}</div>
          <div><h5>Alertas recientes</h5>{li(ale)}</div>
        </div>
        <div class="foot">Las alertas ya se han gestionado por los canales de Farmacovigilancia y Medical: no se retoman en visita.</div>
        </div>""",
        unsafe_allow_html=True,
    )
    if b.compromisos:
        with st.expander("Gestionar compromisos pendientes", icon=":material/task_alt:"):
            for r, o in b.compromisos:
                cc1, cc2 = st.columns([4, 1])
                cc1.markdown(f"{'**VENCIDO** · ' if o else ''}{r.siguiente_paso} · _{r.responsable_siguiente_paso or '—'}_ · {fmt(r.fecha_seguimiento)}")
                if cc2.button("Hecho", key=f"done_{r.visita_id}", icon=":material/check:"):
                    mark_followup_done(r.visita_id)
                    st.rerun()

    ui.section("◆", f"Línea de tiempo · {b.n_visitas} visitas")
    items = []
    for row in acc_rows:
        rec = record_of(row)
        short = {"posible_efecto_adverso": "Farmacovigilancia", "pregunta_fuera_ficha": "Fuera de ficha",
                 "solicitud_informacion_medica": "Info. médica"}
        alerts = [short[n] for n in ALERT_UI if getattr(rec.alertas, n).detectado]
        status = {"si": ui.badge("objetivo cumplido", "ok"), "parcial": ui.badge("objetivo parcial", "n"),
                  "no": ui.badge("objetivo no cumplido", "no")}.get(rec.objetivo_cumplido or "", "")
        items.append(
            f'<div class="tl-item{" alerted" if alerts else ""}"><span class="when">{fmt(rec.fecha)}</span>'
            f'<span class="who">{ui.esc(rec.interlocutor_rol)} · {ui.esc(rec.canal or "")}</span>&nbsp;&nbsp;{status}'
            + "".join(ui.badge(a, "alert") for a in alerts)
            + (ui.badge("demo", "n") if row["demo"] else "")
            + f'<div class="txt">{ui.esc(rec.resumen_crm)}</div>'
            f'<div class="nxt"><b>Siguiente paso</b> · {ui.esc(rec.siguiente_paso or "—")}'
            f'{" · " + fmt(rec.fecha_seguimiento) if rec.fecha_seguimiento else ""}{" · ✓ hecho" if row["seguimiento_hecho"] else ""}</div></div>'
        )
    st.markdown(f'<div class="tl">{"".join(items)}</div>', unsafe_allow_html=True)

    ui.section("◆", "Integración")
    st.download_button("Exportar visitas.csv para Territory Scope", visitas_csv(), "visitas.csv", "text/csv",
                       icon=":material/hub:")


# ------------------------------------------------------------------ 5 · weekly dashboard
def _bar_theme(chart):
    return (chart.configure(font="IBM Plex Sans", background="#FFFFFF")
            .configure_view(stroke=None)
            .configure_axis(labelColor="#636B74", titleColor="#636B74", labelFontSize=13, titleFontSize=12,
                            gridColor="#EEF3F8", domain=False, tickColor="#D5DEE8"))


def page_weekly() -> None:
    import altair as alt

    from src.weekly import available_weeks, generate_report, summarize, visits_frame

    ui.hero("Weekly · para el manager", "Panel <em>semanal</em>",
            "Cobertura frente al plan, resultados, seguimientos y alertas gestionadas de la semana. "
            "El informe con IA recibe solo cifras agregadas: ni cuentas, ni nombres, ni notas.")
    df = visits_frame()
    weeks = available_weeks(df)
    if not weeks:
        st.info("Todavía no hay visitas aprobadas. Carga las visitas sintéticas desde «Historial por cuenta».")
        return
    c1, _ = st.columns([1, 2])
    monday = c1.selectbox("Semana", weeks, format_func=lambda d: f"Semana del {d:%d/%m/%Y}")
    s = summarize(df, monday)
    plan_total = sum(s.plan_por_segmento.values())
    sin_dato = s.objetivos.get("sin dato", 0)
    ui.kpis([
        ("Visitas vs plan", f"{s.visitas}<small>/ {plan_total}</small>" if plan_total else str(s.visitas), f"{s.cuentas_visitadas} cuentas visitadas"),
        ("Objetivo cumplido", f"{s.objetivos.get('si', 0)}<small>/ {s.visitas}</small>", f"{sin_dato} visitas sin dato"),
        ("Seguimientos vencidos", str(s.seguimientos_vencidos), f"de {s.seguimientos_pendientes} pendientes", s.seguimientos_vencidos > 0),
        ("Alertas gestionadas", f"{s.alertas_confirmadas}<small>/ {s.alertas_total}</small>", "confirmadas por la KAM"),
    ])

    left, right = st.columns(2, gap="large")
    with left:
        ui.section("01", "Cobertura por segmento")
        cov = pd.DataFrame([{"Segmento": seg, "Visitas": s.visitas_por_segmento[seg], "Plan": s.plan_por_segmento[seg]}
                            for seg in s.visitas_por_segmento])
        base = alt.Chart(cov).encode(y=alt.Y("Segmento:N", title=None, sort=["A", "B", "C"], axis=alt.Axis(labelPadding=8)))
        bars = base.mark_bar(color="#1F4E79", height=22, cornerRadiusEnd=4).encode(
            x=alt.X("Visitas:Q", title="Visitas (barra) frente al plan (marca)", axis=alt.Axis(tickMinStep=1)),
            tooltip=["Segmento", "Visitas", "Plan"])
        ticks = base.mark_tick(color="#0B1929", thickness=3, size=34).encode(x="Plan:Q", tooltip=["Segmento", "Visitas", "Plan"])
        labels = base.mark_text(align="left", dx=8, color="#1F2328", fontSize=13).encode(x="Visitas:Q", text="Visitas:Q")
        st.altair_chart(_bar_theme((bars + ticks + labels).properties(height=180)), width="stretch")
    with right:
        ui.section("02", "Objeciones por tipo")
        if s.objeciones_por_tipo:
            obj = pd.DataFrame([{"Tipo": k, "Objeciones": v} for k, v in s.objeciones_por_tipo.items()])
            ob = alt.Chart(obj).encode(y=alt.Y("Tipo:N", title=None, sort="-x", axis=alt.Axis(labelLimit=220, labelPadding=8, minExtent=110)))
            chart = (ob.mark_bar(color="#1F4E79", height=22, cornerRadiusEnd=4).encode(
                        x=alt.X("Objeciones:Q", title="Objeciones registradas", axis=alt.Axis(tickMinStep=1)),
                        tooltip=["Tipo", "Objeciones"])
                     + ob.mark_text(align="left", dx=8, color="#1F2328", fontSize=13).encode(x="Objeciones:Q", text="Objeciones:Q"))
            st.altair_chart(_bar_theme(chart.properties(height=180)), width="stretch")
        else:
            st.caption("Sin objeciones registradas esta semana.")

    left, right = st.columns([1.4, 1], gap="large")
    with left:
        ui.section("03", "Seguimientos pendientes")
        rows = "".join(
            f'<div class="tl-item{" alerted" if p["vencido"] else ""}" style="padding:.6rem .9rem;margin-bottom:.5rem">'
            f'{ui.badge("vencido", "alert") if p["vencido"] else ""}<span class="when">{fmt(p["fecha_seguimiento"])}</span>'
            f'<span class="who">cuenta {ui.esc(p["cuenta_id"])} · {ui.esc(p["responsable"] or "—")}</span>'
            f'<div class="nxt" style="margin-top:.2rem;color:#1F2328">{ui.esc(p["siguiente_paso"])}</div></div>'
            for p in s.pendientes[:8])
        st.markdown(f'<div class="tl">{rows}</div>', unsafe_allow_html=True)
        if len(s.pendientes) > 8:
            st.caption(f"… y {len(s.pendientes) - 8} más en «Historial por cuenta».")
    with right:
        ui.section("04", "Alertas de compliance")
        st.markdown("".join(
            f'<div class="kpi" style="margin-bottom:.6rem;padding:.7rem 1rem"><div class="lab">{ui.esc(k)}</div>'
            f'<div class="val" style="font-size:1.6rem">{v}</div></div>' for k, v in s.alertas_detectadas.items()),
            unsafe_allow_html=True)
        st.caption("Cada alerta se confirma antes de aprobar la ficha; la notificación sigue el procedimiento de la compañía.")

    ui.section("05", "Informe semanal con IA")
    payload = s.report_payload()
    with st.expander("Datos exactos que recibe la IA (solo agregados)", icon=":material/shield:"):
        st.json(payload)
    key = f"informe_{monday.isoformat()}"
    if st.button("Generar borrador del informe", type="primary", icon=":material/auto_awesome:"):
        try:
            with st.spinner("Redactando con la IA local…"):
                st.session_state[key] = generate_report(s)
        except Exception as e:  # noqa: BLE001
            st.error(f"No se ha podido generar el informe: {e}")
    if key in st.session_state:
        texto = st.text_area("Borrador (revísalo y edítalo antes de compartirlo)", st.session_state[key], height=300, key=f"{key}_edit")
        st.download_button("Descargar informe (.md)", texto, f"informe_semanal_{monday:%Y%m%d}.md", "text/markdown",
                           icon=":material/download:")
        st.caption("La app no envía nada: el informe lo compartes tú.")

    ui.section("06", "Integración")
    st.download_button("Exportar visitas.csv para Territory Scope", visitas_csv(), "visitas.csv", "text/csv", icon=":material/hub:")


# ------------------------------------------------------------------ 6 · methodology & privacy
def page_method() -> None:
    ui.hero("Metodología · privacidad", "Cómo funciona y qué <em>no</em> sale del equipo",
            "Compliance por diseño: la IA propone, la KAM decide, y ningún dato de paciente llega al modelo.")
    left, right = st.columns([1.2, 1], gap="large")
    with left:
        ui.section("01", "El recorrido de una nota")
        st.markdown(
            "1. **Captura.** La KAM dicta su resumen a solas, *después* de la visita, o lo escribe. La app nunca graba la visita.\n"
            "2. **Transcripción local** con Whisper (faster-whisper, modelo *small*). El audio se borra al transcribirlo.\n"
            "3. **Bloqueo de conversaciones.** Si el texto parece un diálogo (turnos, preguntas directas, muletillas), se rechaza "
            "antes de llegar a la IA y se pide un dictado.\n"
            "4. **Anonimización** con reglas (DNI/NIE, SIP, historia clínica, teléfonos, emails, fechas de nacimiento, números largos) "
            "y reconocimiento de nombres con spaCy: pacientes → `[PACIENTE]`, edades → `[EDAD]`, médicos → su rol. Una última "
            "comprobación impide el envío si queda algún identificador.\n"
            "5. **Estructuración** con un modelo local (Ollama · Qwen 3.5) y salida en un esquema JSON fijo. Fechas, SMART y "
            "campos faltantes se calculan con reglas, no con la IA.\n"
            "6. **Alertas de compliance**: IA **o** reglas (basta con una). Mejor un falso positivo que un efecto adverso perdido.\n"
            "7. **Revisión y aprobación** de la KAM: cada alerta exige su casilla antes de aprobar. Nada se guarda sin aprobación.\n"
            "8. **Salidas**: registro CRM (CSV/JSON), recordatorio .ics y borrador de email. La app no envía nada.")
    with right:
        ui.section("02", "Qué recibe la IA")
        st.markdown(
            "- **Sí:** el texto ya anonimizado, la fecha de la visita y el rol del interlocutor.\n"
            "- **No:** el audio, nombres de pacientes o médicos, identificadores, el nombre de la cuenta.\n"
            "- **Informe semanal:** solo recuentos y categorías (ver el panel semanal).\n"
            "- Todo se ejecuta en el portátil de la KAM; en la demo pública se usan fichas ya generadas.")
        ui.section("03", "Resultados en 20 notas sintéticas")
        st.markdown(
            "| | Sensibilidad | Especificidad |\n|---|---|---|\n"
            "| Posible efecto adverso (3) | 100 % | 100 % |\n"
            "| Pregunta fuera de ficha (3) | 100 % | 100 % |\n"
            "| Información médica (5) | 100 % | 93 % |\n\n"
            "**0** identificadores de paciente en el texto enviado al modelo · conversación grabada detectada **20/20** · "
            "campos clave autocompletados **78 %** de media · nota → ficha aprobada **57 s** en la demo grabada.")
        ui.section("04", "Limitaciones")
        st.markdown(
            "- 20 notas y 3 casos por alerta es una muestra pequeña; las reglas se ajustaron viendo esas notas.\n"
            "- Whisper puede equivocarse en palabras clave: el fragmento de cada alerta se puede corregir antes de aprobar.\n"
            "- La detección de conversaciones se basa en el texto, no distingue voces.\n"
            "- Herramienta de apoyo: **no sustituye** los procedimientos de Farmacovigilancia ni de Información Médica.")


nav = st.navigation([
    st.Page(page_new_visit, title="Nueva visita", icon=":material/mic:", default=True),
    st.Page(page_history, title="Historial por cuenta", icon=":material/insights:"),
    st.Page(page_weekly, title="Panel semanal", icon=":material/monitoring:"),
    st.Page(page_method, title="Metodología y privacidad", icon=":material/verified_user:"),
])
if DEMO:
    st.sidebar.markdown(
        '<div style="margin-top:1rem;padding:.6rem .7rem;border:1px solid #2A425A;border-radius:6px;font-size:.78rem;color:#C9D3DC">'
        '<b style="color:#fff">Demo pública</b><br>Notas y fichas sintéticas, generadas en local con la IA. '
        'Lo que escribas aquí no se envía a ninguna IA.</div>', unsafe_allow_html=True)
nav.run()
ui.sidebar_trust(MODEL, CFG["transcription"]["model"])
