"""LLM providers. Each takes (system, user) and returns a validated VisitExtraction.

- ollama (default): free, runs on the KAM's laptop — nothing leaves the machine.
- anthropic: optional paid API (needs ANTHROPIC_API_KEY).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import ValidationError

from schema.visit_record import VisitExtraction

ROOT = Path(__file__).resolve().parent.parent


class ModelRefusalError(RuntimeError):
    pass


class LLMOutputError(RuntimeError):
    pass


def _ollama(system: str, user: str, cfg: dict) -> VisitExtraction:
    import ollama

    schema = VisitExtraction.model_json_schema()
    # The `format` schema constrains decoding; putting it in the prompt as well
    # lets the model read the field descriptions.
    system_full = (
        f"{system}\n\n## Formato de salida\n\nResponde únicamente con un objeto JSON que cumpla este esquema:\n"
        f"```json\n{json.dumps(schema, ensure_ascii=False)}\n```"
    )
    client = ollama.Client(host=cfg.get("host"))
    try:
        resp = client.chat(
            model=cfg["model"],
            messages=[{"role": "system", "content": system_full}, {"role": "user", "content": user}],
            format=schema,
            think=cfg.get("think", False),
            options={"temperature": cfg.get("temperature", 0), "num_ctx": cfg.get("num_ctx", 8192)},
            keep_alive=cfg.get("keep_alive", "30s"),
        )
    except ConnectionError as e:
        raise LLMOutputError("No se puede conectar con Ollama. ¿Está abierto?") from e
    try:
        return VisitExtraction.model_validate_json(resp.message.content)
    except ValidationError as e:
        raise LLMOutputError(f"El modelo devolvió una ficha no válida: {e}") from e


def _anthropic(system: str, user: str, cfg: dict) -> VisitExtraction:
    import anthropic
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        try:  # Streamlit Cloud
            import streamlit as st

            os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
        except Exception:
            pass
    kwargs: dict = dict(
        model=cfg["model"],
        max_tokens=cfg["max_tokens"],
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=VisitExtraction,
        output_config={"effort": cfg["effort"]},
    )
    if cfg.get("server_side_fallback"):
        kwargs |= dict(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    response = anthropic.Anthropic().beta.messages.parse(**kwargs)
    if response.stop_reason == "refusal":
        raise ModelRefusalError("El modelo ha rechazado procesar la nota.")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise LLMOutputError(f"Respuesta incompleta (stop_reason={response.stop_reason}).")
    return response.parsed_output


DEMO_EXTRACTIONS = ROOT / "data/demo/extracciones_demo.json"
DEMO_REPORT = ROOT / "data/demo/informe_semanal_demo.md"
DEMO_ONLY = ("Demo pública: solo se pueden procesar las notas sintéticas de ejemplo, con fichas generadas previamente por "
             "la IA local. Para procesar tus propias notas, ejecuta la app en local con Ollama.")


def _demo_key(text: str) -> str:
    import re

    text = re.sub(r"\[[^\]]+\]", "[X]", text)   # role/patient tags may differ with the chosen role
    return re.sub(r"\s+", " ", text).strip().lower()


def _demo_index() -> dict[str, dict]:
    import csv

    from src.anonymize import anonymize

    data = json.loads(DEMO_EXTRACTIONS.read_text(encoding="utf-8"))
    idx = {}
    for r in csv.DictReader(open(ROOT / "data/demo/notas_sinteticas.csv", encoding="utf-8")):
        if r["nota_id"] in data:
            idx[_demo_key(anonymize(r["texto"], r["interlocutor_rol"]).text)] = data[r["nota_id"]]
    return idx


def _demo(system: str, user: str, cfg: dict) -> VisitExtraction:
    import re

    m = re.search(r"<nota_kam>\n?(.*?)\n?</nota_kam>", user, re.S)
    hit = _demo_index().get(_demo_key(m.group(1) if m else ""))
    if hit is None:
        raise LLMOutputError(DEMO_ONLY)
    return VisitExtraction.model_validate(hit)


PROVIDERS = {"ollama": _ollama, "anthropic": _anthropic, "demo": _demo}


def call_llm(system: str, user: str, llm_cfg: dict) -> VisitExtraction:
    provider = llm_cfg["provider"]
    return PROVIDERS[provider](system, user, llm_cfg[provider])


def generate_text(system: str, user: str, llm_cfg: dict | None = None) -> str:
    """Free-text generation (weekly report). Same providers as call_llm."""
    from src.config import load_config

    llm_cfg = llm_cfg or load_config()["llm"]
    provider = llm_cfg["provider"]
    cfg = llm_cfg[provider]
    if provider == "ollama":
        import ollama

        client = ollama.Client(host=cfg.get("host"))
        try:
            resp = client.chat(
                model=cfg["model"],
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                think=cfg.get("think", False),
                options={"temperature": 0.2, "num_ctx": cfg.get("num_ctx", 8192)},
                keep_alive=cfg.get("keep_alive", "30s"),
            )
        except ConnectionError as e:
            raise LLMOutputError("No se puede conectar con Ollama. ¿Está abierto?") from e
        return resp.message.content.strip()
    if provider == "anthropic":
        import anthropic

        r = anthropic.Anthropic().messages.create(model=cfg["model"], max_tokens=2000, system=system,
                                                  messages=[{"role": "user", "content": user}])
        if r.stop_reason == "refusal":
            raise ModelRefusalError("El modelo ha rechazado generar el informe.")
        return "".join(b.text for b in r.content if b.type == "text").strip()
    if provider == "demo":
        if DEMO_REPORT.exists():
            return DEMO_REPORT.read_text(encoding="utf-8").strip()
        raise LLMOutputError(DEMO_ONLY)
    raise LLMOutputError(f"Proveedor sin generación de texto: {provider}")
