# 🐾 Project Furbacca
An AI-powered, Matter-enabled animatronic build based on the 2012 Hasbro Furby, running on a Raspberry Pi Zero 2 WH.

## 🛠 Project Architecture
- **Nervous System:** Node.js (TypeScript) handling sensors (GPIO) and high-level logic.
- **Vision System:** Python (env) handling dual GC9A01 circular LCDs via SPI.
- **Bridge:** UDP Loopback (Port 5005) for inter-process communication.

---

## 🚀 Getting Started

### 1. The Vision System (Python)
The eyes run in a dedicated virtual environment to handle high-performance graphics.

**Setup:**
```bash
cd ~/furbacca
python3 -m venv env
source env/bin/activate
pip install adafruit-circuitpython-st7789 numpy pillow
```

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