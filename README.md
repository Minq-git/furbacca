# 🐾 Project Furbacca
An AI-powered, Matter-enabled animatronic build based on the 2012 Hasbro Furby, running on a Raspberry Pi Zero 2 WH.

**Platform:** Raspberry Pi Zero 2 WH (with headers), Debian Trixie (Testing).

## 🛠 Architecture
- **Nervous System:** Node.js (TypeScript), sensors (GPIO), high-level logic.
- **Vision System:** Python (venv), dual GC9A01 circular LCDs via SPI.
- **Bridge:** UDP port 5005. Set `VISION_HOST` (e.g. `furbacca.local`) if the nervous system runs on a different host than the eyes.

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
Shapes: `round`, `sharp`, `half_moon`, `bean`, `oval`, `trapezoid`, `tilted`, `dome`, `pill`.  
Types: `default`, `human`, `dragon`, `demon`.

**If remote commands aren’t received:** On the Pi, allow UDP 5005 (e.g. `sudo ufw allow 5005/udp` and `sudo ufw reload`). Check with `ss -ulnp | grep 5005` that the eyes are bound to `0.0.0.0:5005`.

---

## 🔧 Setup

### Vision (Python / eyes)
Eyes: **vision/py/eyes.py** (UDP 5005), [gc9a01py](https://github.com/russhughes/gc9a01py). Pinout and SPI: **instruction.md** §3.1.

```bash
cd ~/furbacca
bash scripts/setup-fresh.sh
source env/bin/activate
```
Or: `python3 -m venv env`, `source env/bin/activate`, `pip install spidev RPi.GPIO Pillow`, `bash scripts/setup/fetch-gc9a01py.sh`, `bash scripts/setup/fetch-eye-graphics.sh`.

**Optional env:**  
- `SWAP_LEFT_RIGHT_SPI=1` — swap left/right displays.  
- `EYES_SOLID_COLORS=1`, `EYES_GRADIENT=1`, `EYES_RAINBOW=1` — test patterns.  
- `EYES_ANIMATED=0` — still image (default: animated).  
- `EYE_TYPE` — **default**, `human`, `dragon`, `demon`.  
- `EYE_SHAPE` — **round**, `sharp`, `half_moon`, `bean`, `oval`, `trapezoid`, `tilted`, `dome`, `pill`.  
- `SPI_BAUDRATE`, `ANIM_FPS`, `EYE_BUILD_SIZE` — tune if needed.  
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

---

## 🔌 Hardware (BCM / physical)

| Component      | GPIO | Physical | Notes           |
|----------------|------|----------|-----------------|
| Touch (Head)   | 17   | 11       | TTP223          |
| Touch (Belly)  | 22   | 15       | TTP223          |
| SPI SCLK       | 11   | 23       | Eyes            |
| SPI MOSI       | 10   | 19       | Eyes            |
| Eye DC         | 25   | 22       | GC9A01          |
| Eye RST        | 27   | 13       | GC9A01          |
| Eye CS (L)     | 8    | 24       | Left            |
| Eye CS (R)     | 7    | 26       | Right           |

---

## 🤖 Commands & automation
- **`wake-furbacca`** — start all services (eyes + nervous system). Use this.
- **`sudo systemctl status furbacca-eyes`** — if you run eyes as a service (see below).
- **`push-furbacca`** — (Mac) rsync project to the Pi. Use **`--delete`** so the Pi loses old paths (e.g. `vision/eyes.py` after refactor) and matches your Mac layout. Exclude Pi-only dirs so rsync doesn't delete them: `vision/py/gc9a01py` (fetched on the Pi by `scripts/setup/fetch-gc9a01py.sh`; not on the Mac), and optionally `vision/waveshare-lcd-code`, `vision/gc9a01py` (old leftovers). Add to `~/.zshrc`:
  ```bash
  alias push-furbacca='rsync -avz --delete --exclude node_modules --exclude .git --exclude env --exclude dist --exclude vision/py/gc9a01py --exclude vision/waveshare-lcd-code --exclude vision/gc9a01py /Users/brent/Documents/Code/Furbacca/ minqz@furbacca.local:~/furbacca/'
  ```
  Then run `push-furbacca` before testing on the Pi; Pi keeps its own `env`, `dist`, and `vision/py/gc9a01py`. After a refactor, `--delete` removes leftover files on the Pi (e.g. old `vision/eyes.py`) so `wake-furbacca` runs the new code.

**Systemd (eyes only):** To run eyes as a service with UDP on 0.0.0.0, copy and edit the unit:
`sudo cp scripts/furbacca-eyes.service /etc/systemd/system/`
Edit `User`, `WorkingDirectory`, and `ExecStart` paths to match your Pi user and repo path, then:
`sudo systemctl daemon-reload && sudo systemctl enable --now furbacca-eyes`

---

## 📝 Troubleshooting
- **Permission denied:** `sudo chown -R $USER:$USER .`
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
