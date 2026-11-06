"""Phase 2 evaluation on the 20 synthetic notes.

Measures, against the expected answers in notas_sinteticas.csv:
- alert sensitivity / specificity for the LLM alone, the rules alone, and LLM OR rules
- patient identifiers or doctor names in the exact text sent to the model (must be 0)
- conversation detection, processing time, share of fields filled automatically

Usage:  .venv/bin/python -m scripts.evaluate
"""
from __future__ import annotations

import csv
import json
import statistics
import time

from src.anonymize import find_identifiers
from src.config import ROOT, VisitMeta, load_config
from src.structure import ConversationError, process_note
from src.validate import fields_filled_ratio

NOTES = ROOT / "data/demo/notas_sinteticas.csv"
OUT = ROOT / "outputs/fase2"
ALERTS = {
    "posible_efecto_adverso": ("esperado_efecto_adverso", "Posible efecto adverso"),
    "pregunta_fuera_ficha": ("esperado_fuera_ficha", "Pregunta fuera de ficha"),
    "solicitud_informacion_medica": ("esperado_info_medica", "Solicitud de información médica"),
}
SOURCES = {"IA sola": lambda f: "IA" in f, "Reglas solas": lambda f: "reglas" in f, "IA + reglas": lambda f: bool(f)}


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.0f} %" if b else "—"


def _rejected(row: dict, secs: float) -> dict:
    entry = {"nota_id": row["nota_id"], "categoria": row["categoria"], "segundos": round(secs, 1), "fugas": 0,
             "sustituciones": 0, "conversacion_esperada": row["esperado_conversacion"] == "true",
             "conversacion_detectada": True, "campos_auto": None, "avisos": "rechazada antes de enviar"}
    for name, (col, _) in ALERTS.items():
        entry[f"{name}_esperado"] = row[col] == "true"
        entry[f"{name}_fuente"] = ""
    return entry


def main() -> None:
    cfg = load_config()
    segmentos = {r["cuenta_id"]: r["segmento"] for r in csv.DictReader(open(ROOT / cfg["data"]["cuentas_csv"], encoding="utf-8"))}
    rows = list(csv.DictReader(open(NOTES, encoding="utf-8")))
    (OUT / "fichas").mkdir(parents=True, exist_ok=True)
    per_note = []

    for row in rows:
        meta = VisitMeta(row["cuenta_id"], row["interlocutor_rol"], row["fecha"], segmentos.get(row["cuenta_id"]), row["canal"] or None)
        t0 = time.perf_counter()
        try:
            res = process_note(row["texto"], meta)
        except ConversationError:  # rejected locally: nothing reached the model
            per_note.append(_rejected(row, time.perf_counter() - t0))
            print(f"{row['nota_id']}  rechazada: conversación (no se envía nada)")
            continue
        except Exception as e:  # keep going; report the failure
            per_note.append({"nota_id": row["nota_id"], "error": str(e)[:200]})
            print(f"{row['nota_id']}  ERROR {e}")
            continue
        secs = time.perf_counter() - t0
        rec = res.record
        secrets = [s for s in (row["identificadores_paciente"] + "|" + row["nombres_medico"]).split("|") if s]
        leaks = [s for s in secrets if s.lower() in res.sent_text.lower()] + [m for _, m in find_identifiers(res.sent_text)]
        (OUT / "fichas" / f"{row['nota_id']}.json").write_text(rec.model_dump_json(indent=2), encoding="utf-8")
        entry = {
            "nota_id": row["nota_id"], "categoria": row["categoria"], "segundos": round(secs, 1),
            "fugas": len(leaks), "sustituciones": len(res.anon.replacements),
            "conversacion_esperada": row["esperado_conversacion"] == "true",
            "conversacion_detectada": any("conversación" in a for a in rec.avisos_validacion),
            "campos_auto": round(fields_filled_ratio(rec), 3), "avisos": " | ".join(rec.avisos_validacion),
        }
        for name, (col, _) in ALERTS.items():
            entry[f"{name}_esperado"] = row[col] == "true"
            entry[f"{name}_fuente"] = "+".join(getattr(rec.alertas, name).fuente)
        per_note.append(entry)
        flags = " ".join(f"{n[:6]}={entry[f'{n}_fuente'] or '-'}" for n in ALERTS)
        print(f"{row['nota_id']}  {secs:5.1f}s  fugas={len(leaks)}  {flags}")

    ok = [e for e in per_note if "error" not in e]
    with open(OUT / "por_nota.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=sorted({k for e in per_note for k in e}, key=lambda k: (k != "nota_id", k)))
        w.writeheader()
        w.writerows(per_note)

    # ---- summary tables ----
    lines = [f"# Fase 2 — resultados en {len(rows)} notas sintéticas", "",
             f"Modelo: `{cfg['llm']['provider']}` / `{cfg['llm'][cfg['llm']['provider']]['model']}` · "
             f"notas procesadas sin error: {len(ok)}/{len(rows)}", "",
             "## Alertas", "", "| Alerta | Fuente | Sensibilidad | Especificidad | VP | FN | FP | VN |",
             "|---|---|---|---|---|---|---|---|"]
    metrics = {}
    for name, (_, label) in ALERTS.items():
        for src, test in SOURCES.items():
            tp = sum(e[f"{name}_esperado"] and test(e[f"{name}_fuente"]) for e in ok)
            fn = sum(e[f"{name}_esperado"] and not test(e[f"{name}_fuente"]) for e in ok)
            fp = sum(not e[f"{name}_esperado"] and test(e[f"{name}_fuente"]) for e in ok)
            tn = sum(not e[f"{name}_esperado"] and not test(e[f"{name}_fuente"]) for e in ok)
            metrics[(name, src)] = (tp, fn, fp, tn)
            lines.append(f"| {label} | {src} | {pct(tp, tp + fn)} | {pct(tn, tn + fp)} | {tp} | {fn} | {fp} | {tn} |")
    misses = [
        f"- {e['nota_id']} ({e['categoria']}): {ALERTS[n][1]} — esperado {'sí' if e[f'{n}_esperado'] else 'no'}, "
        f"IA {'sí' if 'IA' in e[f'{n}_fuente'] else 'no'}, reglas {'sí' if 'reglas' in e[f'{n}_fuente'] else 'no'}"
        for e in ok for n in ALERTS
        if ("IA" in e[f"{n}_fuente"]) != e[f"{n}_esperado"] or ("reglas" in e[f"{n}_fuente"]) != e[f"{n}_esperado"]
    ]
    processed = [e for e in ok if e["campos_auto"] is not None]
    times = [e["segundos"] for e in processed]
    conv_ok = sum(e["conversacion_detectada"] == e["conversacion_esperada"] for e in ok)
    lines += ["", "## Privacidad", "",
              f"- Identificadores de paciente o nombres de médico en el texto enviado al modelo: **{sum(e['fugas'] for e in ok)}**",
              f"- Sustituciones hechas por el anonimizador: {sum(e['sustituciones'] for e in ok)} "
              f"en {sum(e['sustituciones'] > 0 for e in ok)} notas",
              "", "## Otras métricas", "",
              f"- Conversación detectada correctamente: {conv_ok}/{len(ok)}",
              f"- Tiempo de procesado por nota: mediana {statistics.median(times):.0f} s, máximo {max(times):.0f} s",
              f"- Campos clave rellenados automáticamente: {100 * statistics.mean(e['campos_auto'] for e in processed):.0f} % de media",
              f"- Notas rechazadas por parecer una conversación (nada enviado al modelo): "
              f"{sum(e['campos_auto'] is None for e in ok)}",
              "", "## Discrepancias por nota", "", *(misses or ["- Ninguna"])]
    (OUT / "resultados.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "metricas.json").write_text(json.dumps({f"{n}|{s}": v for (n, s), v in metrics.items()}, indent=1), encoding="utf-8")
    print("\n" + "\n".join(lines))


if __name__ == "__main__":
    main()
