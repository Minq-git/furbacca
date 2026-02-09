# GC9A01 device tree overlay

Source: [juliannojungle/gc9a01-overlay](https://github.com/juliannojungle/gc9a01-overlay) (archived; overlay was merged into Raspberry Pi kernel).

Drives **one** GC9A01 display as a framebuffer (e.g. `/dev/fb1`) on SPI0 CE0. Pins: DC=25, RST=27, BL=18, CS=GPIO 8 (CE0). Same pinout as Furbacca’s **left** eye (see **vision/config.h**).

**Dual eyes:** This overlay uses CE0 only and disables `spidev0.0`. Furbacca uses two displays (CE0 + CE1). So:

- **Single-display test:** Enable this overlay to drive one display via `/dev/fb1` (e.g. mirror HDMI with fbcp, or write to the fb from Python). Good to confirm init/format on your hardware.
- **Dual eyes (eyes.py):** Do **not** enable this overlay; use only `dtparam=spi=on` so both `spidev0.0` and `spidev0.1` are available for **vision/eyes.py**.

## Build (if your Pi doesn’t have gc9a01.dtbo)

```bash
dtc -W no-unit_address_vs_reg -@ -I dts -O dtb -o gc9a01.dtbo gc9a01-overlay.dts
sudo cp gc9a01.dtbo /boot/overlays/
```

## Enable (single display only)

In `/boot/firmware/config.txt` (Bookworm+) or `/boot/config.txt`:

```ini
dtparam=spi=on
dtoverlay=gc9a01
```

Optional parameters: `dtoverlay=gc9a01,speed=40000000,rotate=0,width=240,height=240,fps=50,debug=0`

Reboot, then check: `ls /dev/fb*` (should show fb0 and fb1).

## Reference for userspace

The overlay uses `bgr` and MADCTL `0x36 0x08`. If you match this in userspace (e.g. gc9a01py or WaveShare), use BGR565 and the same init sequence when the fb path looks correct.
