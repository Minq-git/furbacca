# 🐾 Project Furbacca
An AI-powered, Matter-enabled animatronic build based on the 2012 Hasbro Furby, running on a Raspberry Pi Zero 2 WH.

**Platform:** Raspberry Pi Zero 2 WH (with headers), Debian Trixie (Testing).

## 🛠 Project Architecture
- **Nervous System:** Node.js (TypeScript) handling sensors (GPIO) and high-level logic.
- **Vision System:** Python (env) handling dual GC9A01 circular LCDs via SPI.
- **Bridge:** UDP Loopback (Port 5005) for inter-process communication.

---

## 🚀 Getting Started

### 1. The Vision System (Python)
Eyes are driven by **vision/eyes.py** (UDP listener on port 5005) using [russhughes/gc9a01py](https://github.com/russhughes/gc9a01py) via a thin CPython compat layer (**vision/machine_compat**). Pinout: **vision/config.h** (GC9A01 240×240, DC=25, RST=27, CS_L=8, CS_R=7). SPI setup: **vision/BOOT_CONFIG.md**.

**Setup:**
```bash
cd ~/furbacca
python3 -m venv env
source env/bin/activate
# SPI + GPIO (Raspberry Pi)
pip install spidev RPi.GPIO
# Eye image loading
pip install pillow
# Fetch gc9a01py driver (pure-Python GC9A01)
bash scripts/fetch-gc9a01py.sh
```

**Optional env:**  
- `SWAP_LEFT_RIGHT_SPI=1` — swap which physical display is "left" vs "right".  
- `EYES_SOLID_COLORS=1` — show only red/blue (no eye image).  
- `EYES_GRADIENT=1` — show XY gradient on both displays (test pattern, no image file).  
- `EYES_RAINBOW=1` — show circular rainbow (pinwheel) on both displays (test pattern).

**Display test modes (for later testing):**
```bash
# Default: eye image (e.g. vision/graphics/iris.jpg) on both displays
python vision/eyes.py

# XY gradient (red/green sweep)
EYES_GRADIENT=1 python vision/eyes.py

# Rainbow pinwheel (radial hue by angle)
EYES_RAINBOW=1 python vision/eyes.py
```

**Optional — Pi_Eyes-style image on both eyes:**  
Copy Adafruit Pi_Eyes graphics so eyes show an image instead of the red/blue test:
```bash
./scripts/fetch-pi-eyes-graphics.sh
```
Then run eyes as usual; **vision/eyes.py** will use **vision/graphics/iris.jpg** (or **eye.png** if present) on both displays. See **vision/graphics/README.md**.

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
- **Eyes / SPI:** Ensure SPI is enabled (`dtparam=spi=on` in `/boot/firmware/config.txt` or raspi-config). See **vision/BOOT_CONFIG.md** for GC9A01 pinout and fbtft notes.
