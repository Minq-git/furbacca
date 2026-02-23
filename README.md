# 🐾 Project Furbacca
An AI-powered, Matter-enabled animatronic build based on the 2012 Hasbro Furby, running on a Raspberry Pi Zero 2 WH.

**Platform:** Raspberry Pi Zero 2 WH (with headers), Debian Trixie (Testing).

## 🛠 Architecture

- **Nervous system** (Node.js/TypeScript): Orchestrates startup, touch, voice, and Matter; loads **brain** and talks to **vision** over UDP.
- **Brain** (`brain/ts/`): Matter lobe — Furbacca as a Matter device (Extended Color Light + Generic Switches); custom Identify server for eye effects.
- **Vision** (`vision/py/`): Python (venv), dual GC9A01 circular LCDs via SPI; **vision/ts/eye_bridge.ts** sends UDP commands to **main_eyes.py**.
- **Senses** (`senses/touch.ts`): Head touch (BCM 17), belly touch (BCM 22), vibration (BCM 23); event-driven (gpiomon) or polling.
- **Homeostasis** (`homeostasis/fan_control.ts`): Dual-fan harness on BCM 24 via 2N2222 NPN; libgpiod + software PWM (~100 Hz), soft-start 0→100% over 2 s for stable fan control during LCD eye rendering.
- **Synapses** (`synapses/`): Shared UDP message shapes (TS interfaces + Python dataclasses) for port 5005 (NS → eyes) and 5006 (camera → NS). See **synapses/README.md**.
- **Voice** (`voice/ts/`, `voice/assets/`): Non-blocking WAV playback via aplay (ALSA); test tone generator.
- **Bridge:** UDP 5005 (nervous system → eyes), 5006 (camera/eye-track → nervous system). Set `VISION_HOST` (e.g. `furbacca.local`) if eyes run on another host.

### File structure

```
furbacca/
├── brain/              # Matter node, high-level decision making (TS)
├── homeostasis/        # Fan control, thermal watchdogs (TS)
├── senses/             # Touch polling, PIR motion, GPIO (TS)
├── synapses/           # Shared UDP message schemas (TS + Python)
│   ├── README.md       # Explains the UDP port mappings (5005, 5006)
│   ├── ts/
│   │   ├── index.ts            # Exports all schemas
│   │   └── vision_messages.ts  # TS interfaces for eye commands and camera events
│   └── py/
│       ├── __init__.py
│       └── vision_messages.py  # Python dataclasses matching the TS interfaces
├── vision/             # Display system and camera tracking
│   ├── ts/             # EyeBridge (Node.js UDP client)
│   └── py/             # Python rendering and hardware loops
│       ├── main_eyes.py
│       ├── camera/     # IMX500 / OpenCV tracking logic
│       ├── engine/     # NumPy matrix math, shapes, blink logic
│       ├── hardware/   # GC9A01 SPI init, blit, machine_compat
│       └── assets/     # config.py, image loaders, /graphics
├── voice/              # Audio playback, ALSA mixing, test tones (TS)
└── scripts/
    ├── wake-furbacca.sh        # Main entry point
    ├── fe-restart.sh           # Quick panic-button reset
    ├── README.md               # Documentation for all scripts
    ├── setup/                  # Installation & environment
    │   ├── setup-fresh.sh
    │   ├── fetch-eye-graphics.sh
    │   └── fetch-gc9a01py.sh
    ├── diagnostics/            # Health checks & hardware tests (the "Vet")
    │   ├── audio-check.sh
    │   ├── monitor-zram.sh
    │   ├── heal-network.sh
    │   └── test-fan.ts
    ├── matter/                 # Smart home / ecosystem utilities
    │   ├── show-matter-pairing.sh
    │   └── matter-factory-reset.sh
    ├── vision/                 # Tools for the optical system
    │   ├── run-eyes.sh
    │   ├── eye-command.sh
    │   └── eye-track.sh
    └── systemd/                # OS-level service definitions
        ├── furbacca.service
        └── furbacca-eyes.service
```

---

## 🚀 Starting the services

**Use `wake-furbacca` to start every service** (eyes + nervous system, and on the Pi **eye-tracking** by default) from the repo root on the Pi:

```bash
./scripts/wake-furbacca.sh
```
To skip starting eye-tracking: **`./scripts/wake-furbacca.sh --no-eye-track`** or **`FURBACCA_EYE_TRACK=0 ./scripts/wake-furbacca.sh`** (short: **`-n`**).

Or on the Pi, alias once and run from anywhere (alias must run the **script**, not an old `python vision/py/main_eyes.py` command):
```bash
alias wake-furbacca='~/furbacca/scripts/wake-furbacca.sh'
wake-furbacca
```
If you see `vision/py/main_eyes.py: No such file`, your Pi alias is wrong—run `alias wake-furbacca` and fix it to the line above, or run `~/furbacca/scripts/wake-furbacca.sh` directly.
This starts the eyes in the background (UDP 5005, `UDP_BIND=0.0.0.0` for remote commands) and the nervous system in the foreground (touch, sounds, eye commands). Both log to the same terminal. Ctrl+C stops both and blanks the displays.

**Optional — separate processes (two terminals):** Only if you need eyes or nervous system alone: `./scripts/vision/run-eyes.sh` for eyes; `npm start` for nervous system (use `sudo npm start` if GPIO needs it).

---

## 📡 Sending eye commands (SSH or from your Mac)

While the eyes are running, you can send UDP commands to port 5005.

**On the Pi (SSH):**
```bash
./scripts/vision/eye-command.sh cycle_eye_shape
./scripts/vision/eye-command.sh shape sharp
./scripts/vision/eye-command.sh type dragon
./scripts/vision/eye-command.sh blink
```

**From your Mac** (eyes started with `UDP_BIND=0.0.0.0`): pass the Pi host as the first argument. If you use an alias, include the host so commands reach the Pi (e.g. `alias fe='./scripts/vision/eye-command.sh furbacca.local'`).
```bash
./scripts/vision/eye-command.sh furbacca.local shape sharp
./scripts/vision/eye-command.sh furbacca.local type human
```
Shapes: `round`, `sharp`, `half_moon`, `bean`, `oval`, `tilted`, `dome`, `pill`, `anime`, `concern`, `glare`, `gemini`, `heart`, `kawaii`, `stern`, `sus`.  
Types: `default`, `human`, `dragon`, `demon`.

**If remote commands aren’t received:** On the Pi, allow UDP 5005 (e.g. `sudo ufw allow 5005/udp` and `sudo ufw reload`). Check with `ss -ulnp | grep 5005` that the eyes are bound to `0.0.0.0:5005`.

**Eyes full re-init (one or both panels black):** One action only — full hardware re-init (RST + init both panels). **Remote:** run **`./scripts/fe-restart.sh`** on the Pi or **`./scripts/fe-restart.sh furbacca.local`** from your Mac. **Touch:** hold **head + belly** together for **5 seconds** (same effect). Use when one or both eyes black out (e.g. after Matter startup or shared-SPI glitches).

---

## 🔧 Setup

### Reinstall after wiping the Pi
1. **On your Mac:** From repo root run **`push-furbacca`** (see Commands & automation for the alias; use your Pi user and host, e.g. `minqz@furbacca.local:~/furbacca/`).
2. **On the Pi (SSH):** Enable SPI (or let the setup script do it), **reboot** if SPI was off, then run the single setup script:
   - **Enable SPI via SSH:** `sudo raspi-config nonint do_spi 0` then `sudo reboot`. (Or run `setup-fresh.sh` first—it enables SPI when possible and then you reboot.)
   ```bash
   cd ~/furbacca
   bash scripts/setup/setup-fresh.sh
   ```
   The script installs Node.js v20 (64-bit via NodeSource if missing), **enables SPI**, **memory tuning** (systemd-zram-generator: 100% of RAM, zstd; zram-tools masked to avoid race; 512 MB disk swap as fallback; gpu_mem=32), **gpiod + libgpiod-dev** (for cooling fan on BCM 24), Python venv, pip deps, gc9a01py, eye graphics, `npm install`/`npm run build`, **wake-furbacca** alias, and **furbacca systemd service** (enabled at boot; start with `sudo systemctl start furbacca` when ready). **Reboot** after the script if it changed SPI, swap, or gpu_mem so those take effect.
3. **Test:** `./scripts/wake-furbacca.sh` (or `wake-furbacca` in a new shell).
4. **Boot (optional):** See **Systemd (full stack at startup)** below to run Furbacca on boot.

### Vision (Python / eyes)
Eyes: **vision/py/main_eyes.py** (UDP 5005), [gc9a01py](https://github.com/russhughes/gc9a01py). Pinout and SPI: **instruction.md** §3.1.

```bash
cd ~/furbacca
bash scripts/setup/setup-fresh.sh
source env/bin/activate
```
Or: `python3 -m venv env`, `source env/bin/activate`, `pip install spidev RPi.GPIO Pillow numpy`, `bash scripts/setup/fetch-gc9a01py.sh`, `bash scripts/setup/fetch-eye-graphics.sh`. NumPy gives smooth 15–30 FPS; if the display is tinted blue, set `EYES_NUMPY_SWAP_RB=1`.

**Optional env:**  
- `SWAP_LEFT_RIGHT_SPI=1` — swap left/right displays.  
- `EYES_SOLID_COLORS=1`, `EYES_GRADIENT=1`, `EYES_RAINBOW=1` — test patterns.  
- `EYES_ANIMATED=0` — still image (default: animated).  
- `EYE_TYPE` — **default**, `human`, `dragon`, `demon`.  
- `EYE_SHAPE` — **round**, `sharp`, `half_moon`, `bean`, `oval`, `tilted`, `dome`, `pill`, `anime`, `concern`, `glare`, `gemini`, `heart`, `kawaii`, `stern`, `sus`.  
- `ANIM_FPS` — target FPS (default **30**; use 15 for toy style or 60 if Pi keeps up).  
- `EYES_NUMPY_SWAP_RB=1` — if NumPy gives a blue tint and the channel check shows BGR, set this. If the check shows RGB but you still get a blue tint, use `EYES_USE_NUMPY_BLIT=0` to force the fallback (correct colors, slower FPS).  
- `SPI_BAUDRATE`, `EYE_BUILD_SIZE` — tune if needed.  
- `UDP_BIND=0.0.0.0` — accept eye commands from the network.

**Test modes** (run with `source env/bin/activate`):
```bash
python vision/py/main_eyes.py
EYES_ANIMATED=0 python vision/py/main_eyes.py
EYES_GRADIENT=1 python vision/py/main_eyes.py
EYE_TYPE=dragon python vision/py/main_eyes.py
EYE_SHAPE=sharp python vision/py/main_eyes.py
```
Eye assets: **vision/py/assets/graphics**. Refresh with `./scripts/setup/fetch-eye-graphics.sh`.

### Nervous system (Node.js)
```bash
npm install
npm run build
npm run sync-sounds
```
**`npm start`** runs only **`tsc`** (no sound copy) so wake-furbacca starts quickly. Voice assets are copied once by **setup-fresh.sh** on the Pi; after a fresh clone elsewhere, run **`npm run sync-sounds`** once (or **`npm run build:full`** to build + copy). **4 Ω 2W (two 8 Ω 1W in parallel):** software + ALSA capped at 60% max gain so we stay within 2W and avoid TP4056 overheating. **`npm run generate-test-tone`** generates **voice/assets/test_tone_1w8ohm.wav** (100 Hz–4 kHz steps) for frequency response checks. Run with `npm start` (or `sudo npm start` for GPIO). See **Starting the services** above.

### Linting & formatting (Biome)
The project uses [Biome](https://biomejs.dev/) for formatting and linting TypeScript and Python. Use it for all formatting and safe fixes so style stays consistent.

```bash
# Format all files
npx @biomejs/biome format --write

# Format specific files
npx @biomejs/biome format --write <files>

# Lint files and apply safe fixes to all files
npx @biomejs/biome lint --write

# Lint files and apply safe fixes to specific files
npx @biomejs/biome lint --write <files>

# Format, lint, and organize imports of all files
npx @biomejs/biome check --write

# Format, lint, and organize imports of specific files
npx @biomejs/biome check --write <files>
```

Config: **biome.json** (VCS-aware, uses `.gitignore`; excludes **dist**).

### Matter: Furbacca as a device
Matter is **on by default** when you run `wake-furbacca` (requires **64-bit Node** on the Pi, e.g. `node -p "process.arch"` → `arm64`). Furbacca appears as one Matter device with:
- **Endpoint 1 — Extended Color Light (eyes):** On/off, brightness, color → impulse, animations, eye type (human/dragon/demon). Identify/triggerEffect → blinks and eye effects.
- **Endpoint 2 — Generic Switch (belly):** Momentary; belly touch broadcasts a press.
- **Endpoint 3 — Generic Switch (head):** Momentary; head touch broadcasts a press.
- **Endpoint 4 — Generic Switch (shake):** Momentary; vibration sensor (shiver) broadcasts with cooldown.

Add Furbacca to Google Home or Apple Home via the pairing QR in the logs; pairing data is stored in `.matter/`. **If the service runs at boot**, get the pairing code and QR URL anytime: on the Pi run **`./scripts/matter/show-matter-pairing.sh`**, or from your Mac **`./scripts/matter/show-matter-pairing.sh furbacca.local`**. To disable Matter for troubleshooting: **`FURBACCA_MATTER=0 wake-furbacca`**.


---

## 🔌 Hardware (BCM / physical)

Full pin mapping: **instruction.md** §1.

| Component       | GPIO | Physical | Notes                              |
|-----------------|------|----------|------------------------------------|
| AI Camera       | CSI  | ribbon   | Face/object tracking (planned)     |
| Touch (Head)    | 17   | 11       | TTP223                             |
| Touch (Belly)   | 22   | 15       | TTP223                             |
| Vibration       | 23   | 16       | SW-420 (shaker)                    |
| PIR Motion      | 4    | 7        | AM312 (motion)                     |
| IR Transmitter  | 16   | 36       | TV/Furby blaster (2× IR LEDs)      |
| SPI SCLK        | 11   | 23       | Eyes                               |
| SPI MOSI        | 10   | 19       | Eyes                               |
| Eye DC          | 25   | 22       | GC9A01                             |
| Eye RST         | 27   | 13       | GC9A01                             |
| Eye CS (L)      | 8    | 24       | Left                               |
| Eye CS (R)      | 7    | 26       | Right                              |
| Cooling fans    | 24   | 18       | 2N2222 NPN, libgpiod PWM           |
| MAX98357A I2S   | 18   | 12       | BCLK (not yet plugged in)           |
| MAX98357A I2S   | 19   | 35       | LRC (not yet plugged in)           |
| MAX98357A I2S   | 21   | 40       | DIN (not yet plugged in)           |
| DRV8833 motor   | 12   | 32       | AIN1 (not yet plugged in)          |
| DRV8833 motor   | 13   | 33       | AIN2 (not yet plugged in)          |
| DRV8833 nFAULT  | 5    | 29       | Motor stall detection              |

**AI camera & IR (planned):** Raspberry Pi AI camera (CSI) for face/object tracking and two IR LEDs (BCM 16, pin 36) for TV/Furby blaster are installed; integration with the nervous system (e.g. tracking → eyes, IR send) is planned. See **instruction.md** §1 (AI Camera, IR Transmitter).

**TODO — AI camera:** New process (e.g. Python with picamera2 / OpenCV or libcamera) for face/object detection; stream results to the nervous system (e.g. UDP or pipe) and optionally drive eye look/blink from tracking.

**TODO — IR transmitter:** Drive BCM 16 (e.g. LIRC or raw timing) to send IR codes; expose "send IR" from the nervous system or a small script for TV/Furby codes. Also communicate with a TV.

**TODO — Camera as Matter endpoint:** Expose the AI camera as a Matter endpoint so the live feed can be viewed remotely via Google Home.

**TODO — Build & train custom model:** Build and train a model using the [AITRIOS Raspberry Pi AI Camera tutorial](https://developer.aitrios.sony-semicon.com/en/docs/raspberry-pi-ai-camera/raspberry-pi-ai-camera-tutorial?version=2025-09-30).


**Tomorrow (planning / discuss):** (1) **Triggered “look”:** A way to trigger Furbacca to “look” at something; at that point he focuses on that person/object to analyze it, otherwise he continues looking around as normal. (2) **Alarm vs casual mode:** “Alarm” mode = current behavior (when a human is detected, track them focused). Alternative mode = more casual (look around normally until triggered to focus).

See **docs/AI_CAMERA.md** for how we leverage the Raspberry Pi AI Camera (IMX500), headless verification steps, and eye tracking.

### Cooling (fan harness)

**Fan control logic:** Dual-fan cooling harness driven by a **2N2222 NPN** transistor using **active-high** logic on **BCM 24 (Physical Pin 18)**. Setting BCM 24 HIGH (or PWM duty &gt; 0) turns the fans on.

**Circuit protection:** A **1 kΩ resistor** between BCM 24 and the transistor base limits base current. A **1N4001 flyback diode** across the fan terminals (cathode to 5 V) prevents inductive kickback when the fans are switched off.

**Power handling:** Fans are powered from the **5 V rail**; the transistor emitter is connected to **GND**. The transistor switches the low side (fan between 5 V and collector).

**Implementation:** Fan control on BCM 24 uses **libgpiod** (GPIO character device) and **software PWM** (~100 Hz) so the fans run without a daemon. **homeostasis/fan_control.ts** sets BCM 24 LOW on startup, then ramps PWM 0→100% over 2 s (soft-start) to avoid brownout. Disable with **FURBACCA_FAN=0**. **setup-fresh.sh** installs **gpiod** and **libgpiod-dev**; no daemon required. See **instruction.md** §1 (Cooling fans).

### Power / safe shutdown

**Never pull the 5V pin while the Pi is running.** That’s a forced brownout: it can corrupt the SD card (mid-write) and, with fans on the same rail, add stress from inductive kickback. Always shut down first: run **`sleep-furbacca`** (or **`sudo halt`** / **`sudo shutdown -h now`**), then wait until the green ACT LED stops flickering and stays off (or a very faint solid glow) before disconnecting power. **setup-fresh.sh** adds the **sleep-furbacca** alias (`sudo halt`) to your shell rc.

---

## 🤖 Commands & automation
- **`wake-furbacca`** — start all services (eyes + nervous system). Use this.
- **`sleep-furbacca`** — (on the Pi) safe shutdown: runs **`sudo halt`**. **Never yank the power pin while the Pi is on** — that can corrupt the SD card (mid-write) and stress the fan circuit. Run **`sleep-furbacca`**, wait until the green ACT LED stops flickering and stays off (or faint solid), then disconnect power. **setup-fresh.sh** adds this alias to your shell rc.
- **`eye-track`** — (alias from **setup-fresh.sh** on the Pi) runs **scripts/vision/eye-track.sh**. **wake-furbacca** starts eye-tracking by default on the Pi; disable with **`wake-furbacca --no-eye-track`** or **`FURBACCA_EYE_TRACK=0`**. Manual: **`eye-track on`** | **`eye-track off`** | **`eye-track status`**; foreground: **`eye-track run --print-every 30`**. Alias as **`fe-track`** if you prefer (e.g. **`fe-track furbacca.lan on`** from Mac). Sends UDP to nervous system (127.0.0.1:5006) when tracking on/off. **FURBACCA_SSH_USER** (default `minqz`) for SSH.
- **`sudo systemctl status furbacca`** — if you run the full stack as a service (see below); **`furbacca-eyes`** for eyes-only.
- **`journalctl -u furbacca -f`** — stream the service logs (animations, touch, Matter, etc.) after SSH; `-n 200` for last 200 lines instead of follow.
- **`./scripts/fe-restart.sh`** — full eyes re-init (RST + init both panels). On the Pi: no args. From Mac: **`./scripts/fe-restart.sh furbacca.local`**. Same effect as holding head + belly for 5 seconds. **Head + belly 30s** (no SSH needed): runs **`./scripts/diagnostics/heal-network.sh`** to restart the network stack and optionally restore Wi‑Fi from `/boot/wpa_supplicant.conf` (see **Network dead after brownout** below).
- **`./scripts/matter/show-matter-pairing.sh`** — show Matter passcode, manual pairing code, and QR URL. On the Pi: run with no args. **From Mac:** `./scripts/matter/show-matter-pairing.sh furbacca.local` (SSH to Pi and run there). Uses `FURBACCA_SSH_USER` (default `minqz`) for SSH.
- **`./scripts/diagnostics/monitor-zram.sh`** — live zRAM compression ratio and SD swap usage (Ctrl+C to stop). On the Pi: `./scripts/diagnostics/monitor-zram.sh`. **From Mac:** `./scripts/diagnostics/monitor-zram.sh furbacca.local` (SSH to Pi and run there).
- **`push-furbacca`** — (Mac) rsync project to the Pi. Use **`--delete`** so the Pi loses old paths (e.g. old `vision/eyes.py` after refactor) and matches your Mac layout. Exclude Pi-only dirs so rsync doesn't delete them: `vision/py/gc9a01py` (fetched on the Pi by `scripts/setup/fetch-gc9a01py.sh`; not on the Mac), and optionally `vision/waveshare-lcd-code`, `vision/gc9a01py` (old leftovers). Add to `~/.zshrc`:
  ```bash
  alias push-furbacca='rsync -avz --delete --exclude node_modules --exclude .git --exclude env --exclude dist --exclude vision/py/gc9a01py --exclude vision/waveshare-lcd-code --exclude vision/gc9a01py /Users/brent/Documents/Code/Furbacca/ minqz@furbacca.local:~/furbacca/'
  ```
  Then run `push-furbacca` before testing on the Pi; Pi keeps its own `env`, `dist`, and `vision/py/gc9a01py`. After a refactor, `--delete` removes leftover files on the Pi so `wake-furbacca` runs the new code.

**Systemd (full stack):** **setup-fresh.sh** installs the `furbacca` service but does **not** enable it at boot (so it won't start automatically until you're ready). Start manually: `wake-furbacca` or `sudo systemctl start furbacca`. When stable, enable at boot: `sudo systemctl enable furbacca`. Check status: `sudo systemctl status furbacca`. **View event logs** (animations, touch, Matter) after SSH: `journalctl -u furbacca -f` (stream) or `journalctl -u furbacca -n 200` (last 200 lines). To stop auto-start: `sudo systemctl disable furbacca` (service stays installed; start manually).

**Systemd (eyes only):** To run only eyes as a service (e.g. you run the nervous system manually), use `scripts/furbacca-eyes.service` instead—copy to `/etc/systemd/system/`, edit paths, then `sudo systemctl daemon-reload && sudo systemctl enable --now furbacca-eyes`.

---

## 📝 Troubleshooting
- **Permission denied:** `sudo chown -R $USER:$USER .`
- **pip install fails (spidev/RPi.GPIO): "Python.h: No such file or directory"** — Install Python dev headers and build tools: `sudo apt-get install -y python3-dev build-essential`. Or run **`bash scripts/setup/setup-fresh.sh`**; it installs them before pip.
- **"git: command not found" (fetch-gc9a01py)** — Install git: `sudo apt-get install -y git`, then run **`bash scripts/setup/setup-fresh.sh`** again (or `bash scripts/setup/fetch-gc9a01py.sh`).
- **"JavaScript heap out of memory" (npm run build on Pi)** — **`setup-fresh.sh`** sets Node heap limit and memory tuning: **zram** (systemd-zram-generator: 100% of RAM, zstd; zram-tools masked on Trixie to avoid device race) so the Pi uses compressed RAM before disk swap, plus 512 MB disk swap and gpu_mem=32. Reboot after setup so zram/swap/gpu_mem apply. Verify zram: `zramctl`. If still OOM: `NODE_OPTIONS=--max-old-space-size=256 npm run build`, or increase disk swap: in `/etc/dphys-swapfile` set `CONF_SWAPSIZE=1024`, then `sudo dphys-swapfile swapoff && sudo dphys-swapfile setup && sudo dphys-swapfile swapon`.
- **wake-furbacca says "can't open file ... vision/py/main_eyes.py"** — The Pi is still using an old alias or script that runs the wrong path instead of the repo script. **Find it:** On the Pi run `type wake-furbacca` (or `which wake-furbacca` if it's a script). If it's an **alias**, edit `~/.bashrc` or `~/.zshrc` and set:
  ```bash
  alias wake-furbacca='~/furbacca/scripts/wake-furbacca.sh'
  ```
  If it's a **script** (e.g. in `~/bin` or `/usr/local/bin`), either replace its contents with a one-liner that runs the repo script, or delete it and use the alias above. Then `source ~/.zshrc` (or `~/.bashrc`) or open a new shell and run `wake-furbacca` again.
- **push-furbacca: cannot delete non-empty directory: vision/py/gc9a01py** — That dir is created on the Pi by `scripts/setup/fetch-gc9a01py.sh` and isn't on the Mac, so `--delete` tries to remove it. Add `--exclude vision/py/gc9a01py` to your alias so rsync leaves it on the Pi.
- **push-furbacca: Permission denied (13) when deleting** — Some files on the Pi may be owned by root or another user. Use `--exclude` for those Pi-only dirs, or on the Pi run once: `sudo chown -R minqz:minqz ~/furbacca`, then run `push-furbacca` again.
- **Module not found (Python/eyes):** Run `source env/bin/activate` before Python/eyes.
- **Cannot find module './voice/ts/audio.js' (or similar dist path):** The `dist/` tree is missing compiled files (e.g. after a partial or old build). From repo root do a **clean build:** **`rm -rf dist && npm run build`** (on the Pi: **`rm -rf dist && npm run build:pi`**), then run **wake-furbacca** again. Ensure **voice/ts/** and all source are synced to the Pi before building.
- **Eyes / SPI:** Enable SPI (`dtparam=spi=on`), see **instruction.md** §3.1.
- **fe / touch not working, ss shows 127.0.0.1:5005:** (1) Sync from Mac with **`--delete`**: `push-furbacca` (alias must include `--delete` so the Pi loses old paths and only has `vision/py/`). (2) On the Pi, stop any old eyes: `sudo systemctl stop furbacca-eyes`. (3) Run `wake-furbacca` from `~/furbacca`; you should see `UDP 0.0.0.0:5005` and then `--- Furbacca Nervous System: Modular Edition ---`. If you see "vision/py/main_eyes.py not found", run push-furbacca again. If you see "Port 5005 already in use", stop the other process first.
- **Pi unresponsive / can't SSH (furbacca service looping):** If the service is restarting constantly, get to a local console (monitor + keyboard or serial), log in, then: `sudo systemctl stop furbacca` and `sudo systemctl disable furbacca`. After pushing the latest code, re-run setup-fresh or reinstall the service; the unit now has `RestartSec=10` and `StartLimitBurst=5` so a failing service won’t spin forever.
- **Cooling fan not spinning:** **setup-fresh.sh** installs **gpiod** and **libgpiod-dev**. Ensure your user can access GPIO (e.g. in the `gpio` group: `sudo usermod -aG gpio $USER`, or udev rules). Disable fan: **FURBACCA_FAN=0**. See **instruction.md** §1 (Cooling fans).
- **Touch dead / "gpioget: unable to request lines: Device or resource busy":** Another process is holding the touch GPIO pins (e.g. a previous `wake-furbacca`, `gpiomon`, or the eyes service). Stop all Furbacca processes (Ctrl+C in the terminal running wake-furbacca; `sudo systemctl stop furbacca-eyes` if eyes run as a service), then start again with a single `wake-furbacca`.
- **SSH drops or "Network is unreachable" right after wake-furbacca:** The Pi may have rebooted (OOM or power brownout) or Wi‑Fi may have dropped under load (eyes + Matter + eye tracking use a lot of CPU/memory). **Try:** (1) **Power:** Use a solid 5V 2.5A+ supply; Pi Zero 2 W under full load can brown out on weak USB. (2) **Reconnect:** Wait 30–60 seconds and try **`ssh minqz@furbacca.lan`** again (Wi‑Fi might come back). (3) **Network heal (no SSH needed):** If the Pi is still running and eyes are on, hold **head + belly for 30 seconds** — runs **heal-network.sh** to restart Wi‑Fi and restore from boot backup. (4) **Run as service next time:** **`sudo systemctl start furbacca`** so the stack runs in the background; if SSH drops, reconnect and check **`journalctl -u furbacca -n 100`** to see if the Pi crashed or only lost Wi‑Fi. (5) **Local console:** If you have a monitor + keyboard or serial, log in and run **`dmesg -T | tail -50`** or **`journalctl -b -1 -n 50`** (previous boot) to check for OOM or kernel errors.
- **Network dead after brownout (can't SSH, furbacca.local doesn't resolve):** Brownouts can corrupt Wi‑Fi config or leave the stack hung. **If the Pi is running and eyes are on:** hold **head + belly for 30 seconds** — the nervous system runs **`./scripts/diagnostics/heal-network.sh`** (restarts NetworkManager/dhcpcd, cycles wlan0, and restores Wi‑Fi from a backup if present). **One-time prep** (when you have SSH): **setup-fresh.sh** backs up Wi‑Fi to the boot partition when possible (wpa_supplicant or NetworkManager). If it skipped (e.g. no config yet): **wpa_supplicant:** **`sudo cp /etc/wpa_supplicant/wpa_supplicant.conf /boot/wpa_supplicant.conf`** (or `/boot/firmware/` on some Pi). **NetworkManager (Bookworm/Trixie):** **`sudo cp /etc/NetworkManager/system-connections/*.nmconnection /boot/NetworkManager-connection.nmconnection`**. Log: `~/network_heal.log`. If the Pi is fully offline (no IP), use a monitor + keyboard or re-flash the SD.
- **Matter: "Failed to parse storage value" or startup hang:** Stale or incompatible data in `.matter/`. Stop wake-furbacca, then: `rm -rf .matter && wake-furbacca`. Re-pair Furbacca in Google Home / Apple Home using the new QR or code.
- **Eye tracking fails to start or "picamera2/cv2 not found":** **setup-fresh.sh** installs **python3-picamera2** and **python3-opencv** (picamera2’s IMX500 path uses OpenCV). If the error says **No module named 'cv2'**, run **`sudo apt install -y python3-opencv`**. If it says picamera2 not found, run **`sudo apt install -y python3-picamera2`**. **eye-track.sh** finds a Python that can `import picamera2` and clears **PYTHONPATH** so a local **reference/picamera2** clone doesn’t shadow the system package. If **on** fails, the script prints the last 25 lines of **/tmp/eye-track.log**; if it starts then stops, run **`eye-track`** (no args) to see the last 20 log lines. Foreground: **`eye-track run --print-every 30`**. From Mac: **`eye-track furbacca.lan on`**.
- **No sound from speakers (aplay or head touch):** If **aplay -D plughw:0,0** runs but no sound (and wiring hasn't changed): (1) **Reboot:** **`sudo reboot`** — the I2S driver can get into a bad state. (2) **Power cycle:** Unplug Pi power 5–10 seconds, then plug back in. (3) **Test tone:** **`speaker-test -D plughw:0,0 -c 1 -t sine -f 440 -l 1`** (one beep). (4) **Config:** Ensure **`dtparam=audio=off`** and **`dtoverlay=max98357a,no-sdmode`** in **/boot/firmware/config.txt**; reboot after any change. (5) Run **`./scripts/diagnostics/audio-check.sh`** for a full checklist.
- **Audio works after reboot but stops after wake-furbacca until reboot:** This was caused by **BCM 18** being used for both I2S BCLK (MAX98357A) and the display backlight in **vision/py/display.py**. The display code now uses **backlight = None** so BCM 18 is reserved for I2S. If you still have no sound: reboot; ensure **dtparam=audio=off** and **dtoverlay=max98357a,no-sdmode** in **/boot/firmware/config.txt**; run **./scripts/diagnostics/audio-check.sh**. **FURBACCA_SKIP_AMIXER=1** skips the amixer volume step if your DAC has no software volume.
- **Matter: "Error adding membership for address 224.0.0.251: addMembership ENODEV":** The SDK is trying to join mDNS multicast on an interface that doesn't support it (e.g. down or loopback). Usually **harmless** — Matter still comes online and pairing works. If hubs can't discover Furbacca, pin the interface: **`MATTER_MDNS_NETWORKINTERFACE=wlan0 wake-furbacca`** (or `eth0` if wired).
- **Matter: device shows as "Matter.js Test Vendor" in Google Home:** Ensure you’re on a build that sets `basicInformation` (vendorName/productName, etc.) in `brain/ts/matter_lobe.ts`; re-pair after updating.
