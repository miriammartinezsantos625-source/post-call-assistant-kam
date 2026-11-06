"""Transcription smoke test with a macOS synthetic voice (skipped elsewhere)."""
import os
import shutil
import subprocess
import tempfile

import pytest

pytestmark = pytest.mark.skipif(not shutil.which("say"), reason="needs macOS 'say'")


def test_spanish_dictation_round_trip_and_temp_file_deleted():
    from src.transcribe import transcribe_bytes

    with tempfile.TemporaryDirectory() as d:
        aiff = os.path.join(d, "n.aiff")
        subprocess.run(["say", "-v", "Mónica", "-o", aiff, "Me pregunta si hay datos en niños menores de seis años."], check=True)
        data = open(aiff, "rb").read()
    before = set(os.listdir(tempfile.gettempdir()))
    tr = transcribe_bytes(data, suffix=".aiff")
    assert "menores de" in tr.text.lower() and tr.language == "es"
    assert set(os.listdir(tempfile.gettempdir())) - before == set()  # audio not kept


def test_long_audio_is_rejected():
    from src.transcribe import AudioTooLongError, transcribe_file

    with tempfile.TemporaryDirectory() as d:
        aiff = os.path.join(d, "n.aiff")
        subprocess.run(["say", "-v", "Mónica", "-o", aiff, "Hola."], check=True)
        cfg = {"model": "small", "compute_type": "int8", "language": "es", "max_seconds": 0}
        with pytest.raises(AudioTooLongError):
            transcribe_file(aiff, cfg)
