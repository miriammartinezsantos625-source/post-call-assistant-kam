"""Build data/demo/extracciones_demo.json from the reviewed demo history (one extraction per synthetic note).

In the public demo these replace the local LLM call; everything after it (rules, dates, SMART, alert merge,
validation) still runs for real. Usage: .venv/bin/python -m scripts.build_demo_assets
"""
from __future__ import annotations

import json

from schema.visit_record import VisitExtraction, VisitRecord
from scripts.clean_demo_history import note_id
from src.config import ROOT


def main() -> None:
    out = {}
    for line in (ROOT / "data/demo/historial_demo.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = VisitRecord.model_validate_json(line)
        d = rec.model_dump()
        d["parece_conversacion"] = False
        d["alertas"] = {k: {"detectado": v["detectado"], "fragmento": v["fragmento"]} for k, v in d["alertas"].items()}
        ext = VisitExtraction.model_validate({k: d[k] for k in VisitExtraction.model_fields})
        out[note_id(rec)] = ext.model_dump()
    path = ROOT / "data/demo/extracciones_demo.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(out)} extractions → {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
