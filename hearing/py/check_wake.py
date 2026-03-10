#!/usr/bin/env python3
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportAny=false
"""Read raw PCM (S16_LE 16 kHz mono) from stdin; run Vosk; print WAKE if "hey furbacca" or "furbacca" in transcript.
Model path: VOSK_MODEL env, or voice/models/vosk-model-small-en-us-0.15.
Install: pip install vosk. Download model: https://alphacephei.com/vosk/models (e.g. vosk-model-small-en-us-0.15).

Modes:
  One-shot: read all stdin, process once, print WAKE or nothing.
  Daemon (--daemon): read 4-byte LE length then N bytes in a loop; print WAKE or empty line per chunk. Loads model once.
"""

import json
import os
import struct
import sys
from typing import Any


def is_wake(text: str) -> bool:
    t = text.strip().lower()
    return bool(t and ("furbacca" in t or "fur bah kah" in t or "fur-bah-kah" in t))


def process_chunk(rec: Any, pcm: bytes, debug: bool) -> bool:
    rec.AcceptWaveform(pcm)
    result = json.loads(rec.FinalResult())
    text = (result.get("text") or "").strip().lower()
    if debug and text:
        print(f"Hearing (Vosk): transcript = {text!r}", file=sys.stderr, flush=True)
    return is_wake(text)


def run_daemon(model_path: str) -> None:
    try:
        from vosk import KaldiRecognizer, Model  # pyright: ignore[reportMissingImports]
    except ImportError as e:
        print(f"Hearing (Vosk): import failed: {e}", file=sys.stderr, flush=True)
        return
    model = Model(model_path)
    debug = os.environ.get("FURBACCA_HEARING_DEBUG", "").strip().lower() in ("1", "true", "yes")
    buf = sys.stdin.buffer
    while True:
        len_buf = buf.read(4)
        if not len_buf or len(len_buf) < 4:
            break
        (size,) = struct.unpack("<I", len_buf)
        pcm = buf.read(size)
        if len(pcm) < size:
            break
        try:
            rec = KaldiRecognizer(model, 16000)
            woke = process_chunk(rec, pcm, debug)
            print("WAKE" if woke else "", flush=True)
        except Exception as e:
            print("", flush=True)
            if debug:
                print(f"Hearing (Vosk): {e}", file=sys.stderr, flush=True)


def run_oneshot(model_path: str, pcm: bytes) -> None:
    try:
        from vosk import KaldiRecognizer, Model  # pyright: ignore[reportMissingImports]
    except ImportError as e:
        print(f"Hearing (Vosk): import failed: {e}", file=sys.stderr, flush=True)
        return
    model = Model(model_path)
    rec = KaldiRecognizer(model, 16000)
    debug = os.environ.get("FURBACCA_HEARING_DEBUG", "").strip().lower() in ("1", "true", "yes")
    if process_chunk(rec, pcm, debug):
        print("WAKE", flush=True)


def main() -> None:
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
    if "--daemon" in sys.argv:
        run_daemon(model_path)
        return
    pcm = sys.stdin.buffer.read()
    if not pcm:
        return
    run_oneshot(model_path, pcm)


if __name__ == "__main__":
    main()
