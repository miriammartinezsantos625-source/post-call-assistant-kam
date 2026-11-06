"""Shared paths, config loading and the visit metadata chosen in the UI."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class VisitMeta:
    """Chosen by the KAM in the UI — never inferred by the model."""

    cuenta_id: str
    interlocutor_rol: str
    fecha: str  # YYYY-MM-DD
    segmento: str | None = None
    canal: str | None = None


def is_demo() -> bool:
    """Public demo (Streamlit Cloud): no local LLM; uses records pre-generated locally. Set POSTCALL_DEMO=1."""
    import os

    return os.environ.get("POSTCALL_DEMO", "").strip().lower() in ("1", "true", "yes")


def load_config() -> dict:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    if is_demo():
        cfg["llm"]["provider"] = "demo"
        cfg["llm"].setdefault("demo", {})
    return cfg
