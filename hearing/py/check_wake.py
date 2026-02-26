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
    if not os.path.isdir(model_path):
        return  # No model: silent skip
    try:
        from vosk import KaldiRecognizer, Model  # pyright: ignore[reportMissingImports]
    except ImportError:
        return
    model = Model(model_path)
    rec = KaldiRecognizer(model, 16000)
    rec.AcceptWaveform(pcm)
    result = json.loads(rec.FinalResult())
    text = (result.get("text") or "").strip().lower()
    if not text:
        return
    if "furbacca" in text or "fur bah kah" in text or "fur-bah-kah" in text:
        print("WAKE", flush=True)

if __name__ == "__main__":
    main()
