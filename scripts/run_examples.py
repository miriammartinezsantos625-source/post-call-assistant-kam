"""Phase 1 checkpoint: run the example notes through the configured LLM and save the records.

Usage:  .venv/bin/python -m scripts.run_examples [--dry-run]
"""
from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

from src.structure import ROOT, SYSTEM_PROMPT, VisitMeta, build_user_message, load_config, structure_note

NOTES = ROOT / "data/demo/ejemplos_fase1.csv"
OUT = ROOT / "outputs/fase1"
ALERTS = [
    ("posible_efecto_adverso", "esperado_efecto_adverso"),
    ("pregunta_fuera_ficha", "esperado_fuera_ficha"),
    ("solicitud_informacion_medica", "esperado_info_medica"),
]


def main(dry_run: bool) -> None:
    cuentas = ROOT / load_config()["data"]["cuentas_csv"]
    segmentos = {r["cuenta_id"]: r["segmento"] for r in csv.DictReader(open(cuentas, encoding="utf-8"))}
    OUT.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(open(NOTES, encoding="utf-8")))
    for row in rows:
        meta = VisitMeta(
            cuenta_id=row["cuenta_id"],
            interlocutor_rol=row["interlocutor_rol"],
            fecha=row["fecha"],
            segmento=segmentos.get(row["cuenta_id"]),
            canal=row["canal"] or None,
        )
        if dry_run:
            print(f"--- {row['nota_id']} (system prompt: {len(SYSTEM_PROMPT)} chars)\n{build_user_message(row['texto'], meta)}\n")
            continue
        t0 = time.perf_counter()
        rec = structure_note(row["texto"], meta)
        secs = time.perf_counter() - t0
        (OUT / f"{row['nota_id']}.json").write_text(rec.model_dump_json(indent=2), encoding="utf-8")
        print(f"\n=== {row['nota_id']}  ({secs:.1f}s)  -> outputs/fase1/{row['nota_id']}.json")
        for name, col in ALERTS:
            got = getattr(rec.alertas, name).detectado
            exp = row[col] == "true"
            print(f"  {name:30s} esperado={exp!s:5} detectado={got!s:5} {'OK' if got == exp else 'DIFERENTE'}")
        print(f"  campos_faltantes: {rec.campos_faltantes}")
        if rec.avisos_validacion:
            print(f"  avisos: {rec.avisos_validacion}")


if __name__ == "__main__":
    main("--dry-run" in sys.argv)
