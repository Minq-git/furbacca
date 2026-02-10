# Pi_Eyes and Furbacca Displays

[Adafruit Pi_Eyes](https://github.com/adafruit/Pi_Eyes) is an animated eye project that uses **pi3d** (OpenGL) to render eyes to the framebuffer and **fbx2** (C) to copy that framebuffer to two SPI displays.

## Hardware difference

| | Pi_Eyes (Adafruit) | Furbacca |
|---|--------------------|----------|
| **Displays** | SSD1351 / ST7735 / ST7789 | **GC9A01** (240×240 round) |
| **SPI** | SPI0 (first eye) + **SPI1** (second eye) | **SPI0 only** (spidev0.0 + spidev0.1) |
| **DC / RST** | GPIO 5, 6 | **GPIO 25, 27** (see vision/config.h) |
| **fbx2** | Copies fb → spidev0.0 + spidev1.2 | Would need fb → spidev0.0 + spidev0.1 + GC9A01 init |

Pi_Eyes’ **fbx2** uses two SPI buses and ST7789/SSD1351/ST7735 init. Furbacca uses **one** SPI bus and **GC9A01** init, so the stock fbx2 does not work with our displays.

## Options

1. **Use Furbacca’s vision/eyes.py (current)**  
   - Drives both GC9A01s via **gc9a01py** (Python).  
   - Shows a static eye image (e.g. **vision/graphics/iris.jpg**) or gradient/rainbow test patterns.  
   - Listens on UDP (port 5005) for blink/look from the Node nervous system.  
   - No Pi_Eyes animation; no fbx2.

2. **Run Pi_Eyes on HDMI / framebuffer**  
   - Set up Pi_Eyes and run `eyes.py` (see below).  
   - Eyes render to the default display (HDMI or fb0).  
   - They do **not** appear on the Furbacca GC9A01s unless you add a Furbacca-specific copy step (custom fbx2 or equivalent).

3. **Use Pi_Eyes on Furbacca’s GC9A01s (future)**  
   - Would require a **Furbacca fbx2**: same idea as Adafruit’s fbx2, but:  
     - Single SPI bus: spidev0.0 and spidev0.1.  
     - DC=25, RST=27.  
     - GC9A01 init and window commands (not ST7789).  
   - Then: run Pi_Eyes `eyes.py` (renders to fb) and run the Furbacca fbx2 (copies fb to the two GC9A01s).

## Set up and run Pi_Eyes (HDMI / fb)

```bash
# From repo root
bash scripts/setup-pi-eyes.sh

# Install Pi_Eyes Python deps (in your venv)
pip install pi3d adafruit-blinka svg.path Pillow

# Run Pi_Eyes (renders to default display; needs a display or virtual fb)
cd vision/pi_eyes && python eyes.py
```

Pi_Eyes expects **graphics/eye.svg**, **iris.jpg**, **sclera.png**, **lid.png** under its run directory. The setup script links **vision/pi_eyes/graphics** to **vision/graphics**; add **lid.png** to **vision/graphics** if Pi_Eyes complains (e.g. from a full Pi_Eyes graphics copy).

## Troubleshooting: `'NoneType' object has no attribute 'glActiveTexture'`

pi3d loads OpenGL ES (e.g. `libGLESv2`) at import. If that fails, `opengles` is `None` and you get this error. Common causes:

- **No display / headless:** Running over SSH with no HDMI connected. Pi_Eyes is not headless-friendly; it needs a real display or virtual framebuffer.
- **Pi OS / driver:** On some Pi OS images the GL stack is not available or needs the legacy OpenGL driver. In `/boot/firmware/config.txt` (or `/boot/config.txt`) try enabling the legacy driver: `dtoverlay=vc4-kms-v3d` comment-out or switch to `dtoverlay=vc4-fkms-v3d` and ensure no conflicting GL config.
- **Python 3.13:** pi3d may have compatibility issues on very new Python; if possible try Python 3.11 or 3.12 in the venv.

**Workarounds:** (1) Attach an HDMI display and run `eyes.py` on the Pi with that display active. (2) Use a virtual framebuffer: `sudo apt install xvfb` then `xvfb-run -a python eyes.py` (may still need correct GL libs). (3) Use **vision/eyes.py** for the GC9A01s (no pi3d, static image + blink).

## Summary

- **Furbacca’s displays today:** use **vision/eyes.py** (gc9a01py, static image + blink).  
- **Pi_Eyes today:** use **vision/pi_eyes/eyes.py** for animated eyes on HDMI/fb; to drive the GC9A01s with that animation you’d need a custom **fbx2** (or equivalent) for GC9A01 and our pinout.
