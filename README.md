# 🐾 Project Furbacca

An AI-powered, Matter-enabled animatronic build based on the 2012 Hasbro Furby, running on a Raspberry Pi Zero 2 WH.

**Platform:** Raspberry Pi Zero 2 WH (with headers) | **OS:** Debian Trixie (Testing)

---

## 🛠 Architecture

Furbacca's codebase is structured around physical systems, bridging a Node.js/TypeScript nervous system with a Python hardware/graphics layer over UDP.

* **`brain/` (TS):** High-level orchestration and the Matter Lobe (Furbacca as a smart home device).
* **`vision/` (Py/TS):** Dual GC9A01 circular LCDs via SPI (`optic_nerve`), NumPy matrix rendering (`visual_cortex`), and Picamera2 IMX500 tracking (`retina`).
* **`senses/` (TS):** GPIO polling and event-driven monitoring for touch and spatial awareness.
* **`voice/` (TS):** ALSA audio mixing, sound playback, and vocalizations (I2S DAC).
* **`hearing/` (TS/Py):** Keyword wake phrase (“Hey Furbacca”) via Vosk (offline speech recognition); opens eyes when detected. See `hearing/README.md` and optional env vars in `.env.example`.
* **`homeostasis/` (TS):** Thermal watchdogs and software PWM fan control (libgpiod).
* **`synapses/` (Shared):** The JSON schema/data contract layer bridging TS and Python via UDP (`5005`, `5006`).

---

## 🚀 Quick Start

**Main Entry Point:** Start all services (eyes, nervous system, and eye-tracking).

```bash
./.scripts/wake-furbacca.sh
# OR use the alias if configured:
wake-furbacca
```

**Safe Shutdown:** Safely halt the Pi to prevent SD card corruption or inductive kickback from the fans.

```bash
sleep-furbacca
```

### Updating / Rebooting After Code Changes

After pulling or syncing new code onto the Pi, rebuild TypeScript and restart the stack:

```bash
cd ~/furbacca
npm run build:pi
./.scripts/wake-furbacca.sh
```

If you installed the systemd service instead of running manually:

```bash
cd ~/furbacca
npm run build:pi
sudo systemctl restart furbacca
```

Tip: you can also halt directly from the touch sensors by holding **Head + Belly** for **30 seconds**.

### Sending Eye Commands (UDP 5005)

You can manually send commands to the eyes from the Pi or your local Mac:

```bash
# Shapes: round, sharp, half_moon, bean, oval, tilted, dome, pill, anime, concern, glare, gemini, heart, kawaii, stern, sus
./.scripts/vision/eye-command.sh shape sharp

# Types: default, human, dragon, demon
./.scripts/vision/eye-command.sh type dragon
```

*(Note: To send from a remote machine, pass the host as the first argument, e.g., `./.scripts/vision/eye-command.sh furbacca.local shape sharp`)*

### Wake phrase (“Hey Furbacca”)

Say **“Hey Furbacca”** (or “furbacca” / “fur-bah-kah”) to wake Furbacca: the nervous system listens in short windows (no persistent mic stream), runs Vosk for keyword detection, and opens the eyes when the phrase is heard. Optional: set `VOSK_MODEL` and `FURBACCA_WAKE_RECORD_MS` in `.env`; see `hearing/README.md` and `.env.example`.

---

## 🔌 Hardware & Pinout

| Component | GPIO (BCM) | Physical | Notes |
| :--- | :--- | :--- | :--- |
| **AI Camera** | CSI | Ribbon | IMX500 for object/face tracking |
| **Touch (Head)** | 17 | 11 | TTP223 |
| **Touch (Belly)** | 22 | 15 | TTP223 |
| **Vibration** | 23 | 16 | SW-420 (Shaker) |
| **PIR Motion** | 4 | 7 | AM312 |
| **IR Transmitter** | 16 | 36 | 2x IR LEDs (Planned) |
| **SPI SCLK** | 11 | 23 | Shared Eye SPI |
| **SPI MOSI** | 10 | 19 | Shared Eye SPI |
| **Eye DC** | 25 | 22 | GC9A01 |
| **Eye RST** | 27 | 13 | GC9A01 |
| **Eye CS (Left)** | 8 | 24 | Display 1 |
| **Eye CS (Right)** | 7 | 26 | Display 2 |
| **Cooling Fan** | 26 | 37 | 2N2222 NPN (Active-High PWM) |
| **Audio BCLK** | 18 | 12 | Shared: MAX98357A DAC + Adafruit I2S mic |
| **Audio LRC** | 19 | 35 | Shared: MAX98357A DAC + Adafruit I2S mic |
| **Audio DIN (out)** | 21 | 40 | MAX98357A I2S DAC (playback) |
| **Audio DOUT (in)** | 20 | 38 | Adafruit I2S MEMS Mic SPH0645LM4H #3421 (capture); separate data line from DAC |

Audio playback uses the MAX98357A; the wake phrase (“Hey Furbacca”) uses an **Adafruit I2S MEMS Microphone Breakout – SPH0645LM4H (product #3421)** with data on **BCM 20 (Pin 38)**. They share BCLK and LRC (word select) but use separate data lines. The Pi needs a device tree overlay that exposes **both** as one ALSA card (playback + capture)—e.g. a custom `simple-audio-card` overlay for this wiring. Standard single-device overlays (e.g. `max98357a` alone) only expose playback.

### Schematic

*Furbacca — The Edge AI Animatronic (Rev 1.2, 07 Feb 2026).*

![Furbacca schematic](.docs/Furbacca_schem_v1.2.png)

---

## 🔧 Installation & Setup

### 1. Fresh Pi Setup

Enable SPI (`sudo raspi-config nonint do_spi 0`) and reboot. Then, run the master setup script to install dependencies, configure zRAM, and build the environment:

```bash
cd ~/furbacca
bash .scripts/setup/setup-fresh.sh
```

### 2. Code Synchronization (Mac to Pi)

Add this alias to your local Mac's `~/.zshrc` to safely push code updates:

```bash
alias push-furbacca='rsync -avz --delete --exclude node_modules --exclude .git --exclude env --exclude dist --exclude voice/models --exclude vision/py/gc9a01py /Users/YOUR_PATH/furbacca/ minqz@furbacca.local:~/furbacca/'
```

### 3. Code Quality (Biome, Ruff, Basedpyright & Markdownlint)

Furbacca uses **Biome** (TypeScript) and **Ruff** (Python) for linting and formatting, **Basedpyright** for Python type checking, and **Markdownlint** for Markdown style.

```bash
# Format & Lint everything (run locally)
npx @biomejs/biome check --write
ruff check --fix .

# Python type checking (basedpyright)
basedpyright .
```

To use the **project Python** (venv) for Ruff and Basedpyright, either:

* **Activate the venv once** — then `ruff` and `basedpyright` use the venv:

  ```bash
  source env/bin/activate
  ruff check --fix .
  basedpyright .
  ```

* **Or run the venv binaries directly** (no activation):

  ```bash
  ./env/bin/ruff check --fix .
  ./env/bin/basedpyright .
  ```

---

## 🏠 Matter Integration

Furbacca acts as a native Matter bridge on your network (UDP `5540`).

* **Endpoint 1 (Extended Color Light):** Controls the eyes (brightness/hue maps to species and animations).
* **Endpoints 2-4 (Generic Switches):** Expose the Head, Belly, and Shiver sensors to your smart home.

**To Pair:**
Check the logs during startup for the QR code URL and manual pairing code, or run:

```bash
./.scripts/matter/show-matter-pairing.sh
```

---

## 📝 Troubleshooting

**Audio/I2S is dead or no mic (arecord -l empty):**

* **Why it’s empty:** Your boot config has an I2S overlay that creates the MAX98357A **playback** device (so `aplay -l` shows card 0). That overlay does **not** define an I2S **capture** device, so ALSA has no microphone. You need to enable capture (e.g. add an overlay that exposes I2S mic on GPIO 20).
* **Easiest fix (fresh Pi):** Add the **Google Voice HAT** overlay so the Pi listens for I2S mic data on **GPIO 20** (same BCLK/LRC as your DAC, separate data line). In `/boot/firmware/config.txt` (or `/boot/config.txt`) add **below** your DAC line:
  ```ini
  dtoverlay=googlevoicehat-soundcard
  ```
  Reboot, then run `arecord -l`. You should see a capture device. If capture is on card 1 (or another card), set `FURBACCA_MIC_CARD` to that number in `.env`. The Voice HAT overlay is a generic “simple-audio-card” that expects an I2S mic on GPIO 20 (e.g. SPH0645 / Adafruit #3421).
* **Alternative (same BCLK/LRC, two overlays):** Use `asoc-simple-card` for the DAC and Voice HAT for the mic, e.g. in config: `dtoverlay=asoc-simple-card,card-name="FurbaccaAudio",codec-name="max98357a"` and `dtoverlay=googlevoicehat-soundcard`. Reboot, then `arecord -l`; set `FURBACCA_MIC_CARD` if capture is not card 0.
* If that conflicts or doesn’t work, use a single custom overlay that defines both MAX98357A (playback) and SPH0645 (capture on BCM 20). Run `./.scripts/diagnostics/audio-check.sh` for a summary.
* Ensure `dtparam=audio=off` and `dtparam=i2s=on` in config. After changing overlays, **reboot** and run `arecord -l` to confirm; set `FURBACCA_MIC_CARD` if the mic is not on card 0.

**aplay exits with code 1 (no sound on touch):**

* Confirm playback device: `aplay -l` should list card 0 (MAX98357A). Test manually: `aplay -D plughw:0,0 -q voice/assets/giggle.wav` from repo root.
* Ensure WAVs are present: `ls dist/voice/assets/` (wake-furbacca runs `npm run sync-sounds`).
* If aplay works from the shell but not from the app, try **`FURBACCA_SKIP_AMIXER=1`** (some I2S DACs have no volume control and amixer can put the device in a bad state).

**One or both displays are black / corrupted:**

* Shared SPI buses can occasionally glitch during high-load startups. Trigger a hardware reset by running `./.scripts/fe-restart.sh` or by holding the **Head + Belly** sensors together for 5 seconds.

**Matter fails to start or crashes:**

* Corrupt pairing states can halt the Node.js process. Factory reset the Matter node by running `./.scripts/matter/matter-factory-reset.sh` (or `rm -rf .matter`), then re-pair the device.

**Touch sensors are unresponsive (`Device or resource busy`):**

* Another process is locking the `gpiomon` pins. Stop all services (`sudo systemctl stop furbacca-eyes`), kill zombie processes (`sudo killall gpiomon`), and restart `wake-furbacca`.

**Belly (or head) triggering on its own — phantom touch (TTP223B):**

Capacitive sensors are sensitive to EMI, bad baselines, and power sag. The codebase already uses **80 ms debounce** (touch layer), **800 ms cooldown** between belly actions, and **require release before next press** to reduce software false triggers. If **only one** sensor (e.g. belly, not head) phantom-triggers, the cause is likely specific to that sensor: its **location** (closer to fan/I2S/DAC), **wire route** (e.g. BCM 22 running next to noisy lines), **that module’s** sensitivity/calibration, or something conductive near that pad. If belly still cycles without touch:

* **Wiring:** Keep touch sensor wires **twisted with their own GND**, and away from I2S (pins 18/19) and fan wiring to avoid induced voltage.
* **Baseline:** TTP223B calibrates at power-on. If the sensor was pressed against fur or plastic during boot, it can set a bad baseline and then "rapid-fire" as temp or position changes. Tape the sensor firmly so it isn't wobbling.
* **Sensitivity:** Many TTP223B modules have a small capacitor (C1)—adding 0–50 pF can reduce sensitivity. Avoid conductive foil or metal near the pad.
* **Power sag:** If the DAC draws a spike when playing sound and the 3.3 V rail dips, the sensor can glitch (e.g. giggle → giggle loop). Improve power wiring or add a small bulk cap near the sensor if you see that pattern.

**Network drops under heavy load:**

* Hold **Belly** for 15 seconds. The nervous system will trigger `./.scripts/diagnostics/heal-network.sh` to restart the Wi-Fi stack and recover connection.

**Wake word not working / “model not found” (Vosk):**

* `setup-fresh.sh` downloads the Vosk model on the Pi automatically. The `push-furbacca` rsync excludes `voice/models` so that syncing from the Mac does **not** delete the Pi’s downloaded model (the Mac usually doesn’t have it). If the model is missing (e.g. fresh clone or an older sync without the exclude), on the Pi run: `cd ~/furbacca && bash .scripts/setup/fetch-vosk-model.sh`.
