# 🐾 Project Furbacca
An AI-powered, Matter-enabled animatronic build based on the 2012 Hasbro Furby, running on a Raspberry Pi Zero 2 WH.

**Platform:** Raspberry Pi Zero 2 WH (with headers), Debian Trixie (Testing).

## 🛠 Project Architecture
- **Nervous System:** Node.js (TypeScript) handling sensors (GPIO) and high-level logic.
- **Vision System:** Python (env) handling dual GC9A01 circular LCDs via SPI.
- **Bridge:** UDP Loopback (Port 5005) for inter-process communication. If the nervous system runs on a different host than the eyes (e.g. dev machine vs Pi), set `VISION_HOST` to the Pi’s hostname (e.g. `furbacca.local`) so blink/cycle_eye_type reach the eyes.

---

## 🚀 Getting Started

### 1. The Vision System (Python)
Eyes are driven by **vision/eyes.py** (UDP listener on port 5005) using [russhughes/gc9a01py](https://github.com/russhughes/gc9a01py) via a thin CPython compat layer (**vision/machine_compat**). Pinout: **vision/config.h** (GC9A01 240×240, DC=25, RST=27, CS_L=8, CS_R=7). SPI and boot config: **instruction.md** (§3.1). **Pixel format:** eye/iris image uses **big-endian** RGB565 (`>H`) for correct colours; gradient/rainbow use little-endian (`<H`). See **instruction.md** for details.

**Setup (manual or one-shot):**
```bash
cd ~/furbacca
# One-shot: venv + pip + gc9a01py + Pi_Eyes graphics
bash scripts/setup-fresh.sh
source env/bin/activate
```
Or manually: `python3 -m venv env`, `source env/bin/activate`, `pip install spidev RPi.GPIO Pillow`, `bash scripts/fetch-gc9a01py.sh`, `bash scripts/fetch-eye-graphics.sh`.

**Optional env:**  
- `SWAP_LEFT_RIGHT_SPI=1` — swap which physical display is "left" vs "right".  
- `EYES_SOLID_COLORS=1` — show only red/blue (no eye image).  
- `EYES_GRADIENT=1` — show XY gradient on both displays (test pattern, no image file).  
- `EYES_RAINBOW=1` — show circular rainbow (pinwheel) on both displays (test pattern).
- **Animated eyes are the default.** Set `EYES_ANIMATED=0` for still image (iris + pupil at center, blink on UDP). Animated: iris + moving pupil + blink; UDP `blink`, `look` (x/y), `animation` (e.g. `name: 'nervous_look'`), `cycle_eye_type`.
- `EYE_TYPE` — eye texture/mapping: **default** (current), `human` (inverted + smaller iris), `dragon` (dragon assets + inverted), `demon` (dragon assets, normal mapping).
- `SPI_BAUDRATE` — default **60 MHz** (set lower, e.g. 20000000, if you see tearing or blackout); override if needed.
- `ANIM_FPS` — target fps for animated eyes (default **60**). Lower (e.g. 15, 30) for more time per frame on slow hardware.
- `EYE_BUILD_SIZE` — build eye layer at this size then scale to 240 (default **240** = full res). Lower for faster builds.

**Display test modes (for later testing):**
```bash
# Default: animated eyes (iris + pupil + blink; UDP look x/y)
python vision/eyes.py

# Still image (iris + pupil at center, blink on UDP)
EYES_ANIMATED=0 python vision/eyes.py

# XY gradient (red/green sweep)
EYES_GRADIENT=1 python vision/eyes.py

# Rainbow pinwheel (radial hue by angle)
EYES_RAINBOW=1 python vision/eyes.py

# Dragon eyes (dragon assets + inverted mapping, smaller iris)
EYE_TYPE=dragon python vision/eyes.py

# Demon eyes (dragon assets, normal mapping)
EYE_TYPE=demon python vision/eyes.py

# Human-style mapping (texture bottom = outside of eyeball)
EYE_TYPE=human python vision/eyes.py
```

**Optional — eye image on both eyes:**  
Setup-fresh already fetches eye assets (iris.jpg, sclera.png, etc.) into **vision/graphics**. To fetch or refresh them: `./scripts/fetch-eye-graphics.sh`. **vision/eyes.py** uses **vision/graphics/iris.jpg** (or eye.png) on both displays. See **vision/graphics/README.md** if present.

**Run:**
```bash
# Using the custom alias
wake-furbacca
```

### 2. The Nervous System (Node.js)
Handles touch sensors (P17/P22) and coordinates behaviors.

**Setup:**
```bash
npm install
npm run build
```

**Run:**
```bash
# Requires sudo for GPIO access
sudo npm start
```

---

## 🔌 Hardware Mappings (BCM / Physical)

| Component      | GPIO | Physical Pin | Notes           |
|----------------|------|--------------|-----------------|
| Touch (Head)   | 17   | 11           | TTP223 Sensor   |
| Touch (Belly)  | 22   | 15           | TTP223 Sensor   |
| SPI SCLK       | 11   | 23           | Shared (Eyes)   |
| SPI MOSI       | 10   | 19           | Shared (Eyes)   |
| Eye DC         | 25   | 22           | Data/Command (GC9A01) |
| Eye RST        | 27   | 13           | Reset (GC9A01)  |
| Eye CS (L)     | 8    | 24           | Left Eye Select |
| Eye CS (R)     | 7    | 26           | Right Eye Select |

---

## 🤖 Commands & Automation

- **`wake-furbacca`:** Alias to start the eye listener.
- **`sudo systemctl status furbacca-eyes`:** Check background eye service.
- **`push-furbacca`:** (Mac command) Syncs code from MacBook to Pi.

---

## 📝 Troubleshooting

- **Permission Denied:** Run `sudo chown -R $USER:$USER .` to fix file ownership.
- **Module Not Found:** Ensure `source env/bin/activate` is run before starting the Python script.
- **Eyes / SPI:** Ensure SPI is enabled (`dtparam=spi=on` in `/boot/firmware/config.txt` or raspi-config). See **instruction.md** (§3.1) for GC9A01 pinout and fbtft notes.
