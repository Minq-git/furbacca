#!/usr/bin/env python3
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportAny=false
"""Read raw PCM (S16_LE 16 kHz mono) from stdin; run Vosk; print WAKE if "hey furbacca" or "furbacca" in transcript.
Model path: VOSK_MODEL env, or voice/models/vosk-model-small-en-us-0.15.
Install: pip install vosk. Download model: https://alphacephei.com/vosk/models (e.g. vosk-model-small-en-us-0.15).
"""
import json
import os
import sys


def main() -> None:
    pcm = sys.stdin.buffer.read()
    if not pcm:
        return
    model_path = os.environ.get("VOSK_MODEL", "voice/models/vosk-model-small-en-us-0.15")
    if not os.path.isabs(model_path):
        model_path = os.path.abspath(model_path)
    if not os.path.isdir(model_path):
        print(
            f"Hearing (Vosk): model not found: {model_path}",
            file=sys.stderr,
            flush=True,
        )
        print(
            "  From repo root on the Pi: bash .scripts/setup/fetch-vosk-model.sh",
            file=sys.stderr,
            flush=True,
        )
        return
    try:
        from vosk import KaldiRecognizer, Model  # pyright: ignore[reportMissingImports]
    except ImportError as e:
        print(f"Hearing (Vosk): import failed: {e}", file=sys.stderr, flush=True)
        return
    model = Model(model_path)
    rec = KaldiRecognizer(model, 16000)
    rec.AcceptWaveform(pcm)
    result = json.loads(rec.FinalResult())
    text = (result.get("text") or "").strip().lower()
    if not text:
        return
    debug = os.environ.get("FURBACCA_HEARING_DEBUG", "").strip().lower() in ("1", "true", "yes")
    if debug:
        print(f"Hearing (Vosk): transcript = {text!r}", file=sys.stderr, flush=True)
    if "furbacca" in text or "fur bah kah" in text or "fur-bah-kah" in text:
        print("WAKE", flush=True)

if __name__ == "__main__":
    main()
