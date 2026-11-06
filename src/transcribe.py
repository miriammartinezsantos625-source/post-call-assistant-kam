"""Local speech-to-text with faster-whisper. The audio never leaves the device
and is never stored: callers pass a path or bytes, and temp files are deleted.
"""
from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass
from functools import lru_cache

from src.config import load_config


class AudioTooLongError(ValueError):
    pass


@dataclass
class Transcript:
    text: str
    duration_s: float
    seconds_to_transcribe: float
    language: str
    language_probability: float


@lru_cache(maxsize=2)
def _model(size: str, compute_type: str):
    from faster_whisper import WhisperModel

    return WhisperModel(size, device="cpu", compute_type=compute_type)


def transcribe_file(path: str, cfg: dict | None = None) -> Transcript:
    cfg = cfg or load_config()["transcription"]
    model = _model(cfg["model"], cfg["compute_type"])
    t0 = time.perf_counter()
    segments, info = model.transcribe(
        path,
        language=cfg.get("language", "es"),
        vad_filter=True,  # drop silences
        beam_size=5,
        condition_on_previous_text=False,
        initial_prompt=cfg.get("vocabulario"),
    )
    if info.duration > cfg.get("max_seconds", 180):
        raise AudioTooLongError(
            f"El audio dura {info.duration:.0f} s. Dicta un resumen breve (1–2 min) después de la visita; "
            "no grabes la conversación."
        )
    text = " ".join(s.text.strip() for s in segments).strip()
    return Transcript(text, info.duration, time.perf_counter() - t0, info.language, info.language_probability)


def transcribe_bytes(data: bytes, suffix: str = ".wav", cfg: dict | None = None) -> Transcript:
    """For st.audio_input / uploads: write to a temp file, transcribe, delete."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        return transcribe_file(path, cfg)
    finally:
        os.remove(path)
