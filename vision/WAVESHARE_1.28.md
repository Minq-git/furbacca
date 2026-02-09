# WaveShare 1.28" GC9A01 and Furbacca

**Note:** Furbacca eyes now use [russhughes/gc9a01py](https://github.com/russhughes/gc9a01py) via **vision/display.py** and **vision/machine_compat**. This doc is kept for reference if you want to try WaveShare’s single-display demo (e.g. to verify hardware). To run their demo, download their code manually from WaveShare’s site or clone a mirror; we no longer ship a fetch script for it.

The [Industrial Shields tutorial](https://www.industrialshields.com/blog/raspberry-pi-for-industry-26/1-28-lcd-display-module-raspberry-tutorial-318) shows a working setup for the **WaveShare 1.28" round LCD** (GC9A01) on Raspberry Pi using **WaveShare’s own demo code**.

## What they use

- **Hardware:** Same kind of 1.28" round GC9A01 240×240 display (or very similar).
- **Software:** WaveShare **LCD_Module_RPI_code** (C and Python examples). Use the **Python** demo; the C demo needs **WiringPi**, which is deprecated and not available on Raspberry Pi OS Bookworm / Debian Trixie.
- **Python demo:** `1inch28_LCD_test.py` (RPi.GPIO + spidev, no WiringPi).

## Run WaveShare’s demo (single display)

1. **Fetch the WaveShare code** (we no longer ship a script; download their `LCD_Module_RPI_code.7z` from WaveShare’s wiki and extract, or use a mirror). Install `p7zip-full` if needed: `sudo apt-get install p7zip-full`.

2. **Install deps** (use apt; do not use `pip3 install` system-wide on Bookworm/Trixie):
   ```bash
   sudo apt-get install python3-pil python3-numpy python3-rpi.gpio python3-spidev
   ```
   If `python3-rpi.gpio` or `python3-spidev` are not found, try `python3-gpiozero` and ensure SPI is enabled (raspi-config).

3. **Run the 1.28" test** (one display only). You must **cd into the example folder first**, then run the script. The archive extracts as **LCD_Module_RPI_code** (with "RPI"):
   ```bash
   cd ~/furbacca/vision/waveshare-lcd-code/LCD_Module_RPI_code/RaspberryPi/python/example
   sudo python3 1inch28_LCD_test.py
   ```
   Or as one line: `cd ~/furbacca/vision/waveshare-lcd-code/LCD_Module_RPI_code/RaspberryPi/python/example && sudo python3 1inch28_LCD_test.py`  
   Use the same wiring as in the tutorial (one CS, one DC, one RST). If the clock displays correctly on one eye, your hardware and the WaveShare init/image path are good.

## Next step: both eyes with WaveShare driver

Once the single-display demo works (e.g. clock on the left eye), you can drive **both** eyes with the same init/image logic:

- **Option A:** In **vision/eyes.py**, copy the WaveShare 1.28" init sequence and image-write logic from their `lib/LCD/LCD_1in28.py` (or equivalent) into the ST7789 fallback path so both eyes use the same format that worked in the demo.
- **Option B:** Add the WaveShare Python `lib` folder to `sys.path`, instantiate their display class twice (once with CS = GPIO 8, once with CS = GPIO 7), and use those two display objects in eyes.py for left/right; keep our UDP/blink logic and call their `ShowImage` (or equivalent) for each eye.

Furbacca pinout (from **vision/config.h**): DC=25, RST=27, CS left=8, CS right=7. Match those in the WaveShare driver when adapting for dual display.

## Furbacca vs WaveShare demo

| | WaveShare demo | Furbacca eyes.py |
|---|----------------|------------------|
| Displays | 1 | 2 (left + right) |
| Pins | One CS, DC, RST | DC=25, RST=27, CS_L=8, CS_R=7 (see config.h) |
| Stack | RPi.GPIO + spidev | Blinka + Adafruit ST7789 + custom GC9A01 init |

We drive **two** panels on the same SPI bus (different CS), so we keep using **vision/eyes.py** (ST7789 fallback + GC9A01 init, byte swap, row-by-row image). If the WaveShare demo works on your Pi, you can:

- Use it to confirm one display and wiring.
- Compare their init sequence and pixel format with ours in `vision/eyes.py` (init_cmds, MADCTL, byte order) and align if needed.

## C demo (not recommended on Bookworm / Trixie)

The WaveShare **C** examples are built with **WiringPi** (`USE_WIRINGPI_LIB`). WiringPi is deprecated and not in current Raspberry Pi OS / Debian repos, so the C build fails with `wiringPi.h: No such file or directory`. Use the **Python** demo instead; it only needs RPi.GPIO and spidev.

## If you want to use WaveShare’s driver for both eyes

You’d need to adapt their Python driver to use **two** chip selects (e.g. GPIO 8 and 7), and call it from our UDP/eye logic. Their code would live under `vision/waveshare-lcd-code/` if you download and extract it manually.
