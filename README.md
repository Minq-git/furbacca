# 🐾 Project Furbacca
An AI-powered, Matter-enabled animatronic build based on the 2012 Hasbro Furby, running on a Raspberry Pi Zero 2 WH.

**Platform:** Raspberry Pi Zero 2 WH (with headers), Debian Trixie (Testing).

## 🛠 Architecture
- **Nervous system** (Node.js/TypeScript): Orchestrates startup, touch, sounds, and Matter; loads **brain** and talks to **vision** over UDP.
- **Brain** (`brain/ts/`): Matter lobe — Furbacca as a Matter device (Extended Color Light + Generic Switches); custom Identify server for eye effects.
- **Vision** (`vision/py/`): Python (venv), dual GC9A01 circular LCDs via SPI; **vision/ts/eye_bridge.ts** sends UDP commands to the eyes.
- **Senses** (`senses/touch.ts`): Head touch (BCM 17), belly touch (BCM 22), vibration (BCM 23); event-driven (gpiomon) or polling.
- **Cooling** (`cooling/fan_control.ts`): Dual-fan harness on BCM 24 via 2N2222 NPN; DMA-driven PWM (25 kHz) for stable, jitter-free fan control during LCD eye rendering.
- **Bridge:** UDP port 5005 between nervous system and eyes. Set `VISION_HOST` (e.g. `furbacca.local`) if they run on different hosts.

---

## 🚀 Starting the services

**Use `wake-furbacca` to start every service** (eyes + nervous system) from the repo root on the Pi:

```bash
./scripts/wake-furbacca.sh
```
Or on the Pi, alias once and run from anywhere (alias must run the **script**, not an old `python vision/eyes.py` command):
```bash
alias wake-furbacca='~/furbacca/scripts/wake-furbacca.sh'
wake-furbacca
```
If you see `vision/eyes.py: No such file`, your Pi alias is wrong—run `alias wake-furbacca` and fix it to the line above, or run `~/furbacca/scripts/wake-furbacca.sh` directly.
This starts the eyes in the background (UDP 5005, `UDP_BIND=0.0.0.0` for remote commands) and the nervous system in the foreground (touch, sounds, eye commands). Both log to the same terminal. Ctrl+C stops both and blanks the displays.

**Optional — separate processes (two terminals):** Only if you need eyes or nervous system alone: `./scripts/run-eyes.sh` for eyes; `npm start` for nervous system (use `sudo npm start` if GPIO needs it).

---

## 📡 Sending eye commands (SSH or from your Mac)

While the eyes are running, you can send UDP commands to port 5005.

**On the Pi (SSH):**
```bash
./scripts/eye-command.sh cycle_eye_shape
./scripts/eye-command.sh shape sharp
./scripts/eye-command.sh type dragon
./scripts/eye-command.sh blink
```

**From your Mac** (eyes started with `UDP_BIND=0.0.0.0`): pass the Pi host as the first argument. If you use an alias, include the host so commands reach the Pi (e.g. `alias fe='./scripts/eye-command.sh furbacca.local'`).
```bash
./scripts/eye-command.sh furbacca.local shape sharp
./scripts/eye-command.sh furbacca.local type human
```
Shapes: `round`, `sharp`, `half_moon`, `bean`, `oval`, `tilted`, `dome`, `pill`, `anime`, `concern`, `glare`, `gemini`, `heart`, `kawaii`, `stern`, `sus`.  
Types: `default`, `human`, `dragon`, `demon`.

**If remote commands aren’t received:** On the Pi, allow UDP 5005 (e.g. `sudo ufw allow 5005/udp` and `sudo ufw reload`). Check with `ss -ulnp | grep 5005` that the eyes are bound to `0.0.0.0:5005`.

---

## 🔧 Setup

### Reinstall after wiping the Pi
1. **On your Mac:** From repo root run **`push-furbacca`** (see Commands & automation for the alias; use your Pi user and host, e.g. `minqz@furbacca.local:~/furbacca/`).
2. **On the Pi (SSH):** Enable SPI (or let the setup script do it), **reboot** if SPI was off, then run the single setup script:
   - **Enable SPI via SSH:** `sudo raspi-config nonint do_spi 0` then `sudo reboot`. (Or run `setup-fresh.sh` first—it enables SPI when possible and then you reboot.)
   ```bash
   cd ~/furbacca
   bash scripts/setup-fresh.sh
   ```
   The script installs Node.js v20 (64-bit via NodeSource if missing), **enables SPI**, **memory tuning** (512 MB swap, gpu_mem=32), **pigpio + pigpiod** (enabled at startup so the cooling fan works without sudo), Python venv, pip deps, gc9a01py, eye graphics, `npm install`/`npm run build`, **wake-furbacca** alias, and **furbacca systemd service** (enabled at boot; start with `sudo systemctl start furbacca` when ready). **Reboot** after the script if it changed SPI, swap, or gpu_mem so those take effect.
3. **Test:** `./scripts/wake-furbacca.sh` (or `wake-furbacca` in a new shell).
4. **Boot (optional):** See **Systemd (full stack at startup)** below to run Furbacca on boot.

### Vision (Python / eyes)
Eyes: **vision/py/eyes.py** (UDP 5005), [gc9a01py](https://github.com/russhughes/gc9a01py). Pinout and SPI: **instruction.md** §3.1.

```bash
cd ~/furbacca
bash scripts/setup-fresh.sh
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
python vision/py/eyes.py
EYES_ANIMATED=0 python vision/py/eyes.py
EYES_GRADIENT=1 python vision/py/eyes.py
EYE_TYPE=dragon python vision/py/eyes.py
EYE_SHAPE=sharp python vision/py/eyes.py
```
Eye assets: **vision/py/graphics**. Refresh with `./scripts/setup/fetch-eye-graphics.sh`.

### Nervous system (Node.js)
```bash
npm install
npm run build
```
Run with `npm start` (or `sudo npm start` for GPIO). See **Starting the services** above.

### Matter: Furbacca as a device
Matter is **on by default** when you run `wake-furbacca` (requires **64-bit Node** on the Pi, e.g. `node -p "process.arch"` → `arm64`). Furbacca appears as one Matter device with:
- **Endpoint 1 — Extended Color Light (eyes):** On/off, brightness, color → impulse, animations, eye type (human/dragon/demon). Identify/triggerEffect → blinks and eye effects.
- **Endpoint 2 — Generic Switch (belly):** Momentary; belly touch broadcasts a press.
- **Endpoint 3 — Generic Switch (head):** Momentary; head touch broadcasts a press.
- **Endpoint 4 — Generic Switch (shake):** Momentary; vibration sensor (shiver) broadcasts with cooldown.

Add Furbacca to Google Home or Apple Home via the pairing QR in the logs; pairing data is stored in `.matter/`. **If the service runs at boot**, get the pairing code and QR URL anytime: on the Pi run **`./scripts/show-matter-pairing.sh`**, or from your Mac **`./scripts/show-matter-pairing.sh furbacca.local`**. To disable Matter for troubleshooting: **`FURBACCA_MATTER=0 wake-furbacca`**.


---

## 🔌 Hardware (BCM / physical)

Full pin mapping: **instruction.md** §1.

| Component       | GPIO | Physical | Notes                    |
|-----------------|------|----------|--------------------------|
| Touch (Head)    | 17   | 11       | TTP223                   |
| Touch (Belly)   | 22   | 15       | TTP223                   |
| Vibration       | 23   | 16       | SW-420 (shaker)          |
| SPI SCLK        | 11   | 23       | Eyes                     |
| SPI MOSI        | 10   | 19       | Eyes                     |
| Eye DC          | 25   | 22       | GC9A01                   |
| Eye RST         | 27   | 13       | GC9A01                   |
| Eye CS (L)      | 8    | 24       | Left                     |
| Eye CS (R)      | 7    | 26       | Right                    |
| Cooling fans    | 24   | 18       | 2N2222 NPN, DMA PWM      |
| MAX98357A I2S   | 18   | 12       | Reserved (I2S audio)     |
| MAX98357A I2S   | 19   | 35       | Reserved (I2S audio)     |
| MAX98357A I2S   | 21   | 40       | Reserved (I2S audio)     |
| DRV8833 motor   | 12   | 32       | Furby motor (AIN1)       |
| DRV8833 motor   | 13   | 33       | Furby motor (AIN2)       |

### Cooling (fan harness)

**Fan control logic:** Dual-fan cooling harness driven by a **2N2222 NPN** transistor using **active-high** logic on **BCM 24 (Physical Pin 18)**. Setting BCM 24 HIGH (or PWM duty &gt; 0) turns the fans on.

**Circuit protection:** A **1 kΩ resistor** between BCM 24 and the transistor base limits base current. A **1N4001 flyback diode** across the fan terminals (cathode to 5 V) prevents inductive kickback when the fans are switched off.

**Power handling:** Fans are powered from the **5 V rail**; the transistor emitter is connected to **GND**. The transistor switches the low side (fan between 5 V and collector).

**Implementation:** Fan control on BCM 24 uses **DMA-driven PWM** (pigpio, 25 kHz) so the fans run stably without jitter during concurrent GC9A01 LCD eye rendering. **cooling/fan_control.ts** sets BCM 24 LOW on startup, then ramps PWM 0→100% over 2 s to avoid brownout. Disable with **FURBACCA_FAN=0**. **setup-fresh.sh** installs **pigpio** and enables **pigpiod** at startup so the fan works without sudo. See **instruction.md** §1 (Cooling fans).

### Power / safe shutdown

**Never pull the 5V pin while the Pi is running.** That’s a forced brownout: it can corrupt the SD card (mid-write) and, with fans on the same rail, add stress from inductive kickback. Always shut down first: run **`sleep-furbacca`** (or **`sudo halt`** / **`sudo shutdown -h now`**), then wait until the green ACT LED stops flickering and stays off (or a very faint solid glow) before disconnecting power. **setup-fresh.sh** adds the **sleep-furbacca** alias (`sudo halt`) to your shell rc.

---

## 🤖 Commands & automation
- **`wake-furbacca`** — start all services (eyes + nervous system). Use this.
- **`sleep-furbacca`** — (on the Pi) safe shutdown: runs **`sudo halt`**. **Never yank the power pin while the Pi is on** — that can corrupt the SD card (mid-write) and stress the fan circuit. Run **`sleep-furbacca`**, wait until the green ACT LED stops flickering and stays off (or faint solid), then disconnect power. **setup-fresh.sh** adds this alias to your shell rc.
- **`sudo systemctl status furbacca`** — if you run the full stack as a service (see below); **`furbacca-eyes`** for eyes-only.
- **`journalctl -u furbacca -f`** — stream the service logs (animations, touch, Matter, etc.) after SSH; `-n 200` for last 200 lines instead of follow.
- **`./scripts/show-matter-pairing.sh`** — show Matter passcode, manual pairing code, and QR URL. On the Pi: run with no args. **From Mac:** `./scripts/show-matter-pairing.sh furbacca.local` (SSH to Pi and run there). Uses `FURBACCA_SSH_USER` (default `minqz`) for SSH.
- **`push-furbacca`** — (Mac) rsync project to the Pi. Use **`--delete`** so the Pi loses old paths (e.g. `vision/eyes.py` after refactor) and matches your Mac layout. Exclude Pi-only dirs so rsync doesn't delete them: `vision/py/gc9a01py` (fetched on the Pi by `scripts/setup/fetch-gc9a01py.sh`; not on the Mac), and optionally `vision/waveshare-lcd-code`, `vision/gc9a01py` (old leftovers). Add to `~/.zshrc`:
  ```bash
  alias push-furbacca='rsync -avz --delete --exclude node_modules --exclude .git --exclude env --exclude dist --exclude vision/py/gc9a01py --exclude vision/waveshare-lcd-code --exclude vision/gc9a01py /Users/brent/Documents/Code/Furbacca/ minqz@furbacca.local:~/furbacca/'
  ```
  Then run `push-furbacca` before testing on the Pi; Pi keeps its own `env`, `dist`, and `vision/py/gc9a01py`. After a refactor, `--delete` removes leftover files on the Pi (e.g. old `vision/eyes.py`) so `wake-furbacca` runs the new code.

**Systemd (full stack at startup):** To run `wake-furbacca` (eyes + nervous system) automatically on boot:
```bash
sudo cp scripts/furbacca.service /etc/systemd/system/
```
Edit `User`, `WorkingDirectory`, and `ExecStart` in the unit to match your Pi user and repo path (e.g. `/home/pi/furbacca`), then:
```bash
sudo systemctl daemon-reload && sudo systemctl enable --now furbacca
```
Check status: `sudo systemctl status furbacca`. **View event logs** (animations, touch, Matter) after SSH: `journalctl -u furbacca -f` (stream) or `journalctl -u furbacca -n 200` (last 200 lines).

**Systemd (eyes only):** To run only eyes as a service (e.g. you run the nervous system manually), use `scripts/furbacca-eyes.service` instead—copy to `/etc/systemd/system/`, edit paths, then `sudo systemctl daemon-reload && sudo systemctl enable --now furbacca-eyes`.

---

## 📝 Troubleshooting
- **Permission denied:** `sudo chown -R $USER:$USER .`
- **pip install fails (spidev/RPi.GPIO): "Python.h: No such file or directory"** — Install Python dev headers and build tools: `sudo apt-get install -y python3-dev build-essential`. Or run **`bash scripts/setup-fresh.sh`**; it installs them before pip.
- **"git: command not found" (fetch-gc9a01py)** — Install git: `sudo apt-get install -y git`, then run **`bash scripts/setup-fresh.sh`** again (or `bash scripts/setup/fetch-gc9a01py.sh`).
- **"JavaScript heap out of memory" (npm run build on Pi)** — **`setup-fresh.sh`** sets Node heap limit and memory tuning (512 MB swap, gpu_mem=32). Reboot after setup so swap/gpu_mem apply. If still OOM: `NODE_OPTIONS=--max-old-space-size=256 npm run build`, or increase swap: in `/etc/dphys-swapfile` set `CONF_SWAPSIZE=1024`, then `sudo dphys-swapfile swapoff && sudo dphys-swapfile setup && sudo dphys-swapfile swapon`.
- **wake-furbacca says "can't open file ... vision/eyes.py"** — The Pi is still using an old alias or script that runs `vision/eyes.py` instead of the repo script. **Find it:** On the Pi run `type wake-furbacca` (or `which wake-furbacca` if it's a script). If it's an **alias**, edit `~/.bashrc` or `~/.zshrc` and set:
  ```bash
  alias wake-furbacca='~/furbacca/scripts/wake-furbacca.sh'
  ```
  If it's a **script** (e.g. in `~/bin` or `/usr/local/bin`), either replace its contents with a one-liner that runs the repo script, or delete it and use the alias above. Then `source ~/.zshrc` (or `~/.bashrc`) or open a new shell and run `wake-furbacca` again.
- **push-furbacca: cannot delete non-empty directory: vision/py/gc9a01py** — That dir is created on the Pi by `scripts/setup/fetch-gc9a01py.sh` and isn't on the Mac, so `--delete` tries to remove it. Add `--exclude vision/py/gc9a01py` to your alias so rsync leaves it on the Pi.
- **push-furbacca: Permission denied (13) when deleting** — Some files on the Pi may be owned by root or another user. Use `--exclude` for those Pi-only dirs, or on the Pi run once: `sudo chown -R minqz:minqz ~/furbacca`, then run `push-furbacca` again.
- **Module not found:** Run `source env/bin/activate` before Python/eyes.
- **Eyes / SPI:** Enable SPI (`dtparam=spi=on`), see **instruction.md** §3.1.
- **fe / touch not working, ss shows 127.0.0.1:5005:** (1) Sync from Mac with **`--delete`**: `push-furbacca` (alias must include `--delete` so the Pi loses old `vision/eyes.py` and only has `vision/py/`). (2) On the Pi, stop any old eyes: `sudo systemctl stop furbacca-eyes`. (3) Run `wake-furbacca` from `~/furbacca`; you should see `UDP 0.0.0.0:5005` and then `--- Furbacca Nervous System: Modular Edition ---`. If you see "vision/py/eyes.py not found", run push-furbacca again. If you see "Port 5005 already in use", stop the other process first.
- **Pi unresponsive / can't SSH (furbacca service looping):** If the service is restarting constantly, get to a local console (monitor + keyboard or serial), log in, then: `sudo systemctl stop furbacca` and `sudo systemctl disable furbacca`. After pushing the latest code, re-run setup-fresh or reinstall the service; the unit now has `RestartSec=10` and `StartLimitBurst=5` so a failing service won’t spin forever.
- **Cooling fan not spinning:** **setup-fresh.sh** installs pigpio and enables **pigpiod** at startup. If the fan still doesn’t run, start the daemon manually: `sudo pigpiod`, or run as root. Disable fan: **FURBACCA_FAN=0**.
- **Touch dead / "gpioget: unable to request lines: Device or resource busy":** Another process is holding the touch GPIO pins (e.g. a previous `wake-furbacca`, `gpiomon`, or the eyes service). Stop all Furbacca processes (Ctrl+C in the terminal running wake-furbacca; `sudo systemctl stop furbacca-eyes` if eyes run as a service), then start again with a single `wake-furbacca`.
- **Matter: "Failed to parse storage value" or startup hang:** Stale or incompatible data in `.matter/`. Stop wake-furbacca, then: `rm -rf .matter && wake-furbacca`. Re-pair Furbacca in Google Home / Apple Home using the new QR or code.
- **Matter: device shows as "Matter.js Test Vendor" in Google Home:** Ensure you’re on a build that sets `basicInformation` (vendorName/productName, etc.) in `brain/ts/matter_lobe.ts`; re-pair after updating.
