# Hearing (keyword wake: "Hey Furbacca")

The hearing module listens in **short windows** (no persistent mic stream), so there are no ALSA overruns. Each window is recorded, then checked for the phrase **"Hey Furbacca"** (or "furbacca" / "fur-bah-kah"). If detected, Furbacca opens his eyes and responds.

## Requirements (optional)

Keyword detection uses **Vosk** (offline speech recognition). If Vosk is not installed or no model is present, hearing still runs but will not trigger on the wake phrase.

**Full setup** (on the Pi): `bash .scripts/setup/setup-fresh.sh` installs `vosk` in the venv and runs `.scripts/setup/fetch-vosk-model.sh` to download the small English model to `voice/models/vosk-model-small-en-us-0.15`. The nervous system uses `env/bin/python3` when present so the venv’s Vosk is used.

**Manual:**

1. Install Vosk in the project venv: `source env/bin/activate && pip install vosk`
2. Download the model: `bash .scripts/setup/fetch-vosk-model.sh` (or set `VOSK_MODEL` to your model directory).

## Env vars

- `FURBACCA_HEARING` — Set to `0` to disable hearing (stops mic/wake checks; use when no capture device to avoid log noise).
- `FURBACCA_MIC_CARD` — ALSA capture card (default `0`).
- `FURBACCA_WAKE_RECORD_MS` — Recording window length in ms (default `3000`). No pause between windows; eye sleep is handled elsewhere (e.g. motion timeout).
- `VOSK_MODEL` — Path to Vosk model directory (default `voice/models/vosk-model-small-en-us-0.15`).

## Why is capture failing? (root cause)

We open **`plughw:CARD,0`** for capture; **CARD** defaults to **0**.

Furbacca’s audio hardware is a **MAX98357A** (I2S DAC, playback) and an **Adafruit I2S MEMS mic** (capture), sharing **BCLK** and **LRC** but using **separate data lines**. The Raspberry Pi needs a **single device tree overlay** that exposes both as one ALSA card (playback + capture). The stock **`max98357a`** overlay is **playback-only**, so with only that overlay there is no capture device and `plughw:0,0` fails with "No such file or directory".

**Fix:** Use an overlay that defines both the DAC and the I2S mic (e.g. a custom **simple-audio-card** overlay for your wiring). Then run **`arecord -l`** and confirm a capture device appears. If the mic is on a different card than 0, set **`FURBACCA_MIC_CARD`** to that card number.

At startup, if the configured card has no capture device, the nervous system logs a one-line hint.
