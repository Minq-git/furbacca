# Raspberry Pi GC9A01 / SPI Configuration

Pinout is defined in **vision/config.h** (DC=25, RST=27, CS_L=8, CS_R=7). This file documents how to configure the Pi so SPI and the eyes work.

---

## 1. Enable SPI (required for eyes.py)

On the Pi, either:

- **raspi-config:** `Interface Options` → `SPI` → Enable  
- **Or** add to `/boot/firmware/config.txt` (Bookworm+) or `/boot/config.txt` (older):

```ini
# Enable SPI for GC9A01 eyes (vision/config.h)
dtparam=spi=on
```

Reboot after changing. Verify:

```bash
ls -l /dev/spidev0.0 /dev/spidev0.1
```

You should see both devices (CE0 = GPIO 8, CE1 = GPIO 7).

---

## 2. Userspace drivers (Furbacca: dual eyes)

Furbacca uses **two** GC9A01 displays on the same SPI bus (Left = CS GPIO 8, Right = CS GPIO 7). There is no single kernel overlay that drives both with different CS pins, so we use **userspace**:

- **Python:** `vision/eyes.py` (gc9a01py + spidev/RPi.GPIO compat)

No `dtoverlay=gc9a01` or other fbtft overlay is used for the dual-eye setup. Only `dtparam=spi=on` is required.

---

## 3. Optional: single-display fbtft (gc9a01-overlay)

To drive **one** GC9A01 as a framebuffer (e.g. `/dev/fb1`) use the [gc9a01-overlay](https://github.com/juliannojungle/gc9a01-overlay) (merged into Pi kernel). Pins: DC=25, RST=27, BL=18, CS=GPIO 8 (CE0). **Single display only:** the overlay uses CE0 and disables `spidev0.0`. For dual eyes (eyes.py) do **not** enable the overlay: Python and the kernel would share the DC pin (GPIO 25) and corrupt each other’s signals (garbled display).

```ini
dtparam=spi=on
dtoverlay=gc9a01
```

Optional params: `dtoverlay=gc9a01,speed=40000000,rotate=0,width=240,height=240,fps=50,debug=0`. If `gc9a01.dtbo` is missing, build from the overlay repo or use the Pi kernel overlays.

---

## 4. Summary for Furbacca

| Item              | Value / action |
|-------------------|----------------|
| Pinout            | **vision/config.h** (DC=25, RST=27, CS_L=8, CS_R=7) |
| /boot config      | Add `dtparam=spi=on` (no gc9a01 overlay for dual eyes) |
| Left eye SPI      | `/dev/spidev0.0` (CE0 = GPIO 8) |
| Right eye SPI     | `/dev/spidev0.1` (CE1 = GPIO 7) |
| Python driver     | `vision/eyes.py` |
| SPI speed         | Default 10 MHz; set env `SPI_BAUDRATE=20000000` for faster animated eyes if wiring allows. |
