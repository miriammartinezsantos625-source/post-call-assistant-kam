"""Design system for the Streamlit app.

Restrained palette: navy sidebar (brand area); a workspace of light greys with blue
accents (borders, labels, active states); a single soft red is reserved for compliance
alerts so they stand out.
Type: Source Serif 4 (headings) · IBM Plex Sans (body) · IBM Plex Mono (labels, data).
"""
from __future__ import annotations

import html

import streamlit as st

NAVY, NAVY2, STEEL = "#0B1929", "#13263A", "#9DB6CA"          # sidebar only
INK, TEXT, MUTED, SUBTLE = "#1F2328", "#3A4048", "#636B74", "#8D949B"
LINE, SOFT, BG = "#D5DEE8", "#EEF3F8", "#F4F6F8"
BLUE, BLUE_SOFT, BLUE_LINE = "#1F4E79", "#E7EFF7", "#BFD0E1"   # accent: borders, labels, active states
ALERT, ALERT_BG, ALERT_LINE = "#B4483A", "#FBEFEC", "#EFD3CD"  # compliance only

CSS = f"""
<style>
/* ---------- layout ---------- */
.block-container {{ padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1240px; }}
header[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stToolbar"] {{ visibility: hidden; }}

/* ---------- sidebar (the only coloured area) ---------- */
section[data-testid="stSidebar"] {{ border-right: 1px solid #1E3348; }}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] {{ border-radius: 6px; padding: 0.45rem 0.7rem; }}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] span {{ font-size: 0.92rem; }}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] {{ background: {NAVY2}; box-shadow: inset 3px 0 0 #FFFFFF; }}
section[data-testid="stSidebar"] .stButton button {{ background: transparent; color: #E3E8ED; border: 1px solid #2A425A; font-size: 0.82rem; }}
section[data-testid="stSidebar"] .stButton button:hover {{ border-color: #FFFFFF; color: #FFFFFF; }}

/* ---------- typography ---------- */
.eyebrow {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem; letter-spacing: 0.16em; text-transform: uppercase; color: {BLUE}; margin-bottom: 0.55rem; }}
.hero {{ padding-bottom: 1.3rem; margin-bottom: 1.4rem; border-bottom: 1px solid {LINE}; }}
.hero h1 {{ font-family: 'Source Serif 4', Georgia, serif; font-weight: 500; font-size: 2.45rem; line-height: 1.14; margin: 0 0 0.6rem; padding: 0; color: {INK}; letter-spacing: -0.01em; }}
.hero h1 em {{ font-style: italic; color: {BLUE}; }}
.hero p.lede {{ font-size: 1.02rem; color: {MUTED}; max-width: 760px; line-height: 1.55; margin: 0; }}
.hero p.lede b {{ color: {INK}; font-weight: 600; }}
.sec {{ display: flex; align-items: baseline; gap: 0.7rem; margin: 1.6rem 0 0.8rem; }}
.sec .n {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem; color: {BLUE}; letter-spacing: 0.12em; }}
.sec .t {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.74rem; letter-spacing: 0.14em; text-transform: uppercase; color: {INK}; font-weight: 500; }}
.sec .rule {{ flex: 1; height: 1px; background: {BLUE_LINE}; transform: translateY(-3px); }}
.muted {{ color: {MUTED}; font-size: 0.85rem; }}
.mono {{ font-family: 'IBM Plex Mono', monospace; }}

/* ---------- chips & badges ---------- */
.chips {{ display: flex; flex-wrap: wrap; gap: 0.45rem; margin-top: 0.9rem; }}
.chip {{ font-size: 0.78rem; padding: 0.26rem 0.7rem; border-radius: 999px; background: {BLUE_SOFT}; border: 1px solid {BLUE_LINE}; color: {BLUE}; }}
.badge {{ display: inline-block; font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem; letter-spacing: 0.05em; text-transform: uppercase; padding: 0.15rem 0.5rem; border-radius: 4px; margin-right: 0.3rem; vertical-align: middle; border: 1px solid {LINE}; }}
.b-ok {{ background: {BLUE}; color: white; border-color: {BLUE}; }}
.b-no {{ background: white; color: {SUBTLE}; border-style: dashed; }}
.b-n {{ background: {BLUE_SOFT}; color: {BLUE}; border-color: {BLUE_LINE}; }}
.b-alert {{ background: {ALERT_BG}; color: {ALERT}; border-color: {ALERT_LINE}; }}

/* ---------- stepper ---------- */
.stepper {{ display: grid; grid-template-columns: repeat(5, 1fr); margin: 0 0 1.6rem; border: 1px solid {BLUE_LINE}; border-radius: 10px; overflow: hidden; background: white; }}
.step {{ padding: 0.72rem 0.9rem; border-right: 1px solid {SOFT}; position: relative; }}
.step:last-child {{ border-right: none; }}
.step .k {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem; letter-spacing: 0.12em; color: {SUBTLE}; }}
.step .l {{ font-size: 0.86rem; color: {SUBTLE}; margin-top: 0.15rem; }}
.step.done .k {{ color: {BLUE}; }} .step.done .l {{ color: {TEXT}; }}
.step.now {{ background: {BLUE_SOFT}; }}
.step.now .k {{ color: {BLUE}; }} .step.now .l {{ color: {NAVY}; font-weight: 600; }}
.step.now::after {{ content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 3px; background: {BLUE}; }}

/* ---------- cards ---------- */
div[data-testid="stVerticalBlockBorderWrapper"] {{ background: white; border-color: {LINE} !important; border-radius: 12px; }}
.kpis {{ display: grid; grid-template-columns: repeat(var(--n), 1fr); gap: 0.8rem; margin: 0.2rem 0 1.2rem; }}
.kpi {{ background: white; border: 1px solid {LINE}; border-top: 3px solid {BLUE}; border-radius: 10px; padding: 1rem 1.1rem 0.9rem; }}
.kpi .lab {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem; letter-spacing: 0.12em; text-transform: uppercase; color: {BLUE}; }}
.kpi .val {{ font-family: 'Source Serif 4', Georgia, serif; font-size: 2.1rem; line-height: 1.1; color: {NAVY}; margin-top: 0.35rem; }}
.kpi .val small {{ font-size: 1rem; color: {MUTED}; margin-left: 0.15rem; }}
.kpi .sub {{ font-size: 0.78rem; color: {MUTED}; margin-top: 0.2rem; }}

/* ---------- account snapshot ---------- */
.acct {{ background: white; border: 1px solid {LINE}; border-left: 4px solid {BLUE}; border-radius: 10px; padding: 1.1rem 1.2rem; }}
.acct h3 {{ font-family: 'Source Serif 4', Georgia, serif; color: {INK}; font-weight: 500; font-size: 1.3rem; margin: 0 0 0.15rem; padding: 0; }}
.acct .meta {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0.6rem 1rem; margin-top: 0.9rem; padding-top: 0.9rem; border-top: 1px solid {SOFT}; }}
.acct .meta div span {{ display: block; font-family: 'IBM Plex Mono', monospace; font-size: 0.64rem; letter-spacing: 0.12em; text-transform: uppercase; color: {BLUE}; }}
.acct .meta div b {{ font-weight: 500; color: {INK}; font-size: 0.92rem; }}
.acct .last {{ margin-top: 0.9rem; padding-top: 0.9rem; border-top: 1px solid {SOFT}; font-size: 0.86rem; line-height: 1.5; color: {TEXT}; }}
.acct .last i {{ color: {BLUE}; font-style: normal; font-family: 'IBM Plex Mono', monospace; font-size: 0.66rem; letter-spacing: 0.12em; }}
.howto {{ margin-top: 0.9rem; font-size: 0.84rem; line-height: 1.7; color: {MUTED}; }}

/* ---------- compliance alerts (the only accent colour) ---------- */
.alert {{ background: {ALERT_BG}; border: 1px solid {ALERT_LINE}; border-left: 4px solid {ALERT}; border-radius: 10px; padding: 0.9rem 1rem 0.8rem; margin: 0.2rem 0 0.4rem; }}
.alert .tag {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.66rem; letter-spacing: 0.14em; text-transform: uppercase; color: {ALERT}; font-weight: 500; }}
.alert h4 {{ font-family: 'Source Serif 4', Georgia, serif; font-weight: 600; color: {INK}; font-size: 1.12rem; margin: 0.2rem 0 0.5rem; padding: 0; }}
.alert blockquote {{ margin: 0.35rem 0; padding: 0.1rem 0 0.1rem 0.75rem; border-left: 2px solid {ALERT_LINE}; color: {TEXT}; font-family: 'Source Serif 4', Georgia, serif; font-style: italic; font-size: 0.98rem; }}
.alert .act {{ font-size: 0.88rem; color: {INK}; margin-top: 0.5rem; font-weight: 600; }}
.alert .src {{ font-size: 0.74rem; color: {MUTED}; margin-top: 0.25rem; }}
.ok-panel {{ background: white; border: 1px solid {LINE}; border-left: 4px solid {BLUE}; border-radius: 10px; padding: 0.8rem 1rem; font-size: 0.88rem; color: {TEXT}; }}

/* ---------- executive brief ---------- */
.brief {{ background: white; border: 1px solid {LINE}; border-left: 4px solid {NAVY}; border-radius: 10px; padding: 1.4rem 1.5rem 1.2rem; margin-bottom: 1.2rem; }}
.brief h3 {{ font-family: 'Source Serif 4', Georgia, serif; color: {INK}; font-weight: 500; font-size: 1.5rem; margin: 0 0 0.4rem; padding: 0; }}
.brief .summary {{ font-family: 'Source Serif 4', Georgia, serif; font-style: italic; font-size: 1.05rem; line-height: 1.55; color: {TEXT}; border-left: 2px solid {BLUE_LINE}; padding-left: 0.9rem; margin: 0.6rem 0 1.1rem; }}
.brief .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.1rem; border-top: 1px solid {SOFT}; padding-top: 1rem; }}
.brief .grid h5 {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.66rem; letter-spacing: 0.14em; text-transform: uppercase; color: {BLUE}; margin: 0 0 0.5rem; padding: 0; font-weight: 500; }}
.brief .grid ul {{ list-style: none; padding: 0; margin: 0; }}
.brief .grid li {{ font-size: 0.86rem; line-height: 1.45; margin: 0 0 0.55rem; color: {INK}; }}
.brief .grid li .d {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.7rem; color: {SUBTLE}; }}
.brief .grid li .over {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.62rem; letter-spacing: 0.08em; background: {ALERT_BG}; color: {ALERT}; border: 1px solid {ALERT_LINE}; padding: 0.02rem 0.35rem; border-radius: 3px; margin-right: 0.3rem; }}
.brief .none {{ font-size: 0.84rem; color: {SUBTLE}; }}
.brief .foot {{ font-size: 0.74rem; color: {SUBTLE}; margin-top: 0.6rem; }}

/* ---------- timeline ---------- */
.tl {{ position: relative; margin-left: 0.5rem; padding-left: 1.6rem; border-left: 2px solid {BLUE_LINE}; }}
.tl-item {{ position: relative; background: white; border: 1px solid {LINE}; border-radius: 10px; padding: 0.85rem 1.05rem; margin-bottom: 0.8rem; }}
.tl-item::before {{ content: ""; position: absolute; left: -2.02rem; top: 1.05rem; width: 11px; height: 11px; border-radius: 50%; background: white; border: 2px solid {BLUE}; }}
.tl-item.alerted::before {{ border-color: {ALERT}; background: {ALERT}; }}
.tl-item .when {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.74rem; color: {INK}; font-weight: 500; }}
.tl-item .who {{ font-size: 0.8rem; color: {MUTED}; margin-left: 0.4rem; }}
.tl-item .txt {{ font-size: 0.92rem; line-height: 1.5; margin: 0.4rem 0 0.35rem; color: {TEXT}; }}
.tl-item .nxt {{ font-size: 0.8rem; color: {MUTED}; }}
.tl-item .nxt b {{ color: {INK}; font-weight: 500; }}

/* ---------- deliverables ---------- */
.deliv {{ border: 1px solid {LINE}; border-top: 3px solid {BLUE}; background: white; border-radius: 10px; padding: 1rem 1.1rem 0.4rem; margin-bottom: 0.5rem; }}
.deliv .ic {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.66rem; letter-spacing: 0.14em; color: {BLUE}; text-transform: uppercase; }}
.deliv h4 {{ font-family: 'Source Serif 4', Georgia, serif; font-weight: 500; font-size: 1.12rem; margin: 0.25rem 0 0.3rem; padding: 0; color: {INK}; }}
.deliv p {{ font-size: 0.84rem; color: {MUTED}; margin: 0 0 0.6rem; line-height: 1.45; }}

/* ---------- sticky decision panel ---------- */
div[data-testid="stColumn"]:has(.decision-anchor) {{ position: sticky; top: 1.2rem; align-self: flex-start; }}
.decision-anchor {{ display: none; }}

/* ---------- widgets ---------- */
.stButton button[kind="primary"] {{ background: {NAVY}; border: 1px solid {NAVY}; color: white; font-weight: 500; padding: 0.55rem 1.3rem; }}
.stButton button[kind="primary"]:hover {{ background: {BLUE}; border-color: {BLUE}; color: white; }}
.stButton button[kind="primary"]:disabled {{ background: #D5D9DD; border-color: #D5D9DD; color: #F5F6F7; }}
[data-testid="stWidgetLabel"] p {{ font-size: 0.82rem; font-weight: 500; color: {TEXT}; }}
[data-testid="stExpander"] details {{ background: white; border-radius: 10px; }}
[data-testid="stCheckbox"] label p {{ font-weight: 600; color: {INK}; }}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def esc(s: object) -> str:
    return html.escape(str(s)) if s is not None else ""


def sidebar_trust(model: str, whisper: str) -> None:
    items = ["IA y transcripción 100 % locales", "Anonimización antes de la IA", "Humano en el bucle", "Nada se envía solo"]
    lis = "".join(f'<li style="margin:.38rem 0;">— {i}</li>' for i in items)
    st.sidebar.markdown(
        f"""
        <div style="margin-top:1.6rem;padding-top:1.1rem;border-top:1px solid #1E3348;">
          <div style="font-family:'IBM Plex Mono',monospace;font-size:.62rem;letter-spacing:.16em;color:{STEEL};margin-bottom:.5rem;">COMPLIANCE BY DESIGN</div>
          <ul style="list-style:none;padding:0;margin:0;font-size:.82rem;color:#C9D3DC;">{lis}</ul>
          <div style="margin-top:1rem;font-family:'IBM Plex Mono',monospace;font-size:.66rem;color:#7F93A5;line-height:1.6;">
            LLM · {esc(model)}<br>ASR · whisper-{esc(whisper)}<br>DATOS · 100 % sintéticos
          </div>
        </div>""",
        unsafe_allow_html=True,
    )


def hero(eyebrow: str, title_html: str, lede: str = "", chips: list[str] | None = None) -> None:
    chip_html = ""
    if chips:
        chip_html = '<div class="chips">' + "".join(f'<span class="chip">{esc(c)}</span>' for c in chips) + "</div>"
    st.markdown(
        f'<div class="hero"><div class="eyebrow">{esc(eyebrow)}</div><h1>{title_html}</h1>'
        f'{f"<p class=lede>{lede}</p>" if lede else ""}{chip_html}</div>',
        unsafe_allow_html=True,
    )


def section(n: str, title: str) -> None:
    st.markdown(f'<div class="sec"><span class="n">{esc(n)}</span><span class="t">{esc(title)}</span><span class="rule"></span></div>',
                unsafe_allow_html=True)


STEPS = ["Captura", "Anonimización", "Estructuración IA", "Revisión KAM", "Salidas"]


def stepper(current: int) -> None:
    """current: 0-based index of the active step."""
    cells = []
    for i, label in enumerate(STEPS):
        cls = "done" if i < current else "now" if i == current else ""
        mark = "✓ " if i < current else ""
        cells.append(f'<div class="step {cls}"><div class="k">{mark}{i + 1:02d}</div><div class="l">{label}</div></div>')
    st.markdown(f'<div class="stepper">{"".join(cells)}</div>', unsafe_allow_html=True)


def kpis(items: list[tuple], dark_first: bool = False) -> None:
    """items: (label, value_html, sub[, alert]). An alert tile (overdue, compliance) uses the alert red."""
    cards = ""
    for it in items:
        l, v, sub = it[:3]
        alert = len(it) > 3 and it[3]
        style = f' style="border-top-color:{ALERT}"' if alert else ""
        vstyle = f' style="color:{ALERT}"' if alert else ""
        cards += (f'<div class="kpi"{style}><div class="lab">{esc(l)}</div><div class="val"{vstyle}>{v}</div>'
                  f'<div class="sub">{esc(sub)}</div></div>')
    st.markdown(f'<div class="kpis" style="--n:{len(items)}">{cards}</div>', unsafe_allow_html=True)


def note(text: str) -> None:
    """Neutral, high-contrast notice (replaces Streamlit's yellow warnings)."""
    st.markdown(
        f'<div style="background:white;border:1px solid {LINE};border-left:4px solid {BLUE};border-radius:8px;'
        f'padding:.6rem .9rem;font-size:.86rem;color:{INK};margin:.3rem 0 .5rem;">✎&nbsp; {esc(text)}</div>',
        unsafe_allow_html=True,
    )


def badge(text: str, kind: str = "n") -> str:
    return f'<span class="badge b-{kind}">{esc(text)}</span>'


def alert_card(tag: str, title: str, fragments: list[str], action: str, source: str) -> None:
    quotes = "".join(f"<blockquote>«{esc(f)}»</blockquote>" for f in fragments if f)
    st.markdown(
        f'<div class="alert"><div class="tag">⚠ {esc(tag)}</div><h4>{esc(title)}</h4>{quotes}'
        f'<div class="act">→ {esc(action)}</div><div class="src">{esc(source)}</div></div>',
        unsafe_allow_html=True,
    )


def account_card(cid: str, centro: str, tipo: str, provincia: str, segmento: str, last: str | None, pending: int) -> None:
    last_html = (f'<div class="last"><i>ÚLTIMA VISITA</i><br>{last}</div>' if last
                 else f'<div class="last"><i>ÚLTIMA VISITA</i><br><span style="color:{SUBTLE}">Sin visitas registradas.</span></div>')
    st.markdown(
        f"""<div class="acct"><div class="eyebrow">Contexto de la cuenta</div><h3>{esc(centro)}</h3>
        <div class="muted">Cuenta {esc(cid)} · {esc(provincia)}</div>
        <div class="meta"><div><span>Segmento</span><b>{esc(segmento)}</b></div><div><span>Tipo</span><b>{esc(tipo)}</b></div>
        <div><span>Compromisos abiertos</span><b>{pending}</b></div><div><span>Datos</span><b>Sintéticos</b></div></div>
        {last_html}</div>""",
        unsafe_allow_html=True,
    )
