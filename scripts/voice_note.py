"""Phase 3 checkpoint: a voice note -> transcript -> anonymised -> visit record.

Record from the microphone (press Enter to stop):
    .venv/bin/python -m scripts.voice_note --record --cuenta 4 --rol "jefe de servicio"
Or use an existing file (.m4a, .mp3, .wav):
    .venv/bin/python -m scripts.voice_note --audio ~/Downloads/nota.m4a --cuenta 4 --rol "jefe de servicio"

Recorded audio goes to a temp file that is deleted after transcription. A file you
pass with --audio is never modified or copied.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import queue
import sys
import tempfile
import time

from src.config import ROOT, VisitMeta, load_config
from src.structure import ConversationError, process_note
from src.transcribe import transcribe_file

REMINDER = "Dicta tu resumen después de la visita. No grabes la conversación con el profesional sanitario."
OUT = ROOT / "outputs/fase3"


def record_to_tempfile(max_seconds: int) -> str:
    import sounddevice as sd
    import soundfile as sf

    input("\nPulsa Enter para empezar a grabar…")
    q: queue.Queue = queue.Queue()
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    with sf.SoundFile(path, mode="w", samplerate=16000, channels=1) as f:
        with sd.InputStream(samplerate=16000, channels=1, callback=lambda d, *_: q.put(d.copy())):
            input(f"\n🎙  Grabando (máx. {max_seconds} s). Pulsa Enter para terminar…")
        while not q.empty():
            f.write(q.get())
    return path


def main() -> None:
    cfg = load_config()
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--record", action="store_true")
    src.add_argument("--audio")
    ap.add_argument("--cuenta", required=True)
    ap.add_argument("--rol", required=True, choices=cfg["roles"])
    ap.add_argument("--fecha", default=dt.date.today().isoformat())
    ap.add_argument("--canal", default="presencial", choices=["presencial", "remoto", "telefónico"])
    a = ap.parse_args()

    print(f"\n{REMINDER}")
    temp = None
    try:
        if a.record:
            temp = path = record_to_tempfile(cfg["transcription"]["max_seconds"])
        else:
            path = os.path.expanduser(a.audio)
        print("\nTranscribiendo en local…")
        tr = transcribe_file(path, cfg["transcription"])
    finally:
        if temp and os.path.exists(temp):
            os.remove(temp)  # the recording is never kept
    print(f"Audio de {tr.duration_s:.0f} s transcrito en {tr.seconds_to_transcribe:.0f} s "
          f"(idioma {tr.language}, {tr.language_probability:.0%}).\n\nTRANSCRIPCIÓN:\n{tr.text}\n")

    segs = {r["cuenta_id"]: r["segmento"] for r in csv.DictReader(open(ROOT / cfg["data"]["cuentas_csv"], encoding="utf-8"))}
    meta = VisitMeta(a.cuenta, a.rol, a.fecha, segs.get(a.cuenta), a.canal)
    t0 = time.perf_counter()
    try:
        res = process_note(tr.text, meta)
    except ConversationError as e:
        print(f"⛔ {e}")
        sys.exit(2)
    llm_s = time.perf_counter() - t0

    if res.anon.changed:
        print("ANONIMIZADO antes de procesar:", ", ".join(f"{r.tipo} → {r.sustituto}" for r in res.anon.replacements))
    rec = res.record
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"nota_voz_{dt.datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(rec.model_dump_json(indent=2), encoding="utf-8")

    print("\nALERTAS:")
    for name, al in rec.alertas.model_dump().items():
        if al["detectado"]:
            print(f"  ⚠ {name} [{'+'.join(al['fuente'])}]: «{al['fragmento']}»")
    if not any(al.detectado for al in (rec.alertas.posible_efecto_adverso, rec.alertas.pregunta_fuera_ficha,
                                       rec.alertas.solicitud_informacion_medica)):
        print("  ninguna")
    print(f"\nObjetivo: {rec.objetivo_visita}\nSiguiente paso: {rec.siguiente_paso} "
          f"({rec.fecha_seguimiento_expresion} → {rec.fecha_seguimiento}) · responsable: {rec.responsable_siguiente_paso}")
    print(f"Campos faltantes: {rec.campos_faltantes}")
    if rec.avisos_validacion:
        print("Avisos:", *rec.avisos_validacion, sep="\n  - ")
    print(f"\nResumen CRM ({len(rec.resumen_crm)} car.): {rec.resumen_crm}")
    print(f"\n⏱  transcripción {tr.seconds_to_transcribe:.0f} s + ficha {llm_s:.0f} s "
          f"= {tr.seconds_to_transcribe + llm_s:.0f} s · guardado en {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
