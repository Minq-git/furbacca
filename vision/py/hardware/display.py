"""
Initialize dual GC9A01 displays using russhughes/gc9a01py and machine_compat (CPython on Raspberry Pi).
Pinout: DC=25, RST=27, CS_L=8 (spidev0.0), CS_R=7 (spidev0.1). BL not used — BCM 18 is I2S BCLK (MAX98357A).
See instruction.md §3.1.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable
from typing import Protocol, cast

# vision/py (parent of hardware/) for gc9a01py path
_vision_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _Gc9a01Display(Protocol):
    """Minimal display protocol for gc9a01py panel reinit."""

    def _write(self, *args: object) -> None: ...
    def rotation(self, value: int) -> None: ...


class _BacklightLike(Protocol):
    def value(self, v: int) -> object | None: ...


# Inject MicroPython compat before importing gc9a01py
def _install_compat() -> None:
    # micropython.const
    import types

    micropython = types.ModuleType("micropython")
    setattr(micropython, "const", lambda x: x)
    sys.modules["micropython"] = micropython
    # ustruct
    sys.modules["ustruct"] = __import__("struct")
    # time.sleep_ms
    _sleep = time.sleep
    _ = setattr(time, "sleep_ms", lambda ms: _sleep(ms / 1000.0))


def _sleep_ms(ms: float) -> None:
    """CPython compat for time.sleep_ms (set by _install_compat when running)."""
    _ = getattr(time, "sleep_ms", lambda m: time.sleep(m / 1000.0))(ms)


def _reinit_gc9a01_registers(disp: _Gc9a01Display) -> None:
    """Re-send GC9A01 init register sequence (no RST). Used for left panel after right's hard_reset() resets both."""
    disp._write(0xEF)
    disp._write(0xEB, b"\x14")
    disp._write(0xFE)
    disp._write(0xEF)
    disp._write(0xEB, b"\x14")
    disp._write(0x84, b"\x40")
    disp._write(0x85, b"\xff")
    disp._write(0x86, b"\xff")
    disp._write(0x87, b"\xff")
    disp._write(0x88, b"\x0a")
    disp._write(0x89, b"\x21")
    disp._write(0x8A, b"\x00")
    disp._write(0x8B, b"\x80")
    disp._write(0x8C, b"\x01")
    disp._write(0x8D, b"\x01")
    disp._write(0x8E, b"\xff")
    disp._write(0x8F, b"\xff")
    disp._write(0xB6, b"\x00\x00")
    disp._write(0x3A, b"\x55")
    disp._write(0x90, b"\x08\x08\x08\x08")
    disp._write(0xBD, b"\x06")
    disp._write(0xBC, b"\x00")
    disp._write(0xFF, b"\x60\x01\x04")
    disp._write(0xC3, b"\x13")
    disp._write(0xC4, b"\x13")
    disp._write(0xC9, b"\x22")
    disp._write(0xBE, b"\x11")
    disp._write(0xE1, b"\x10\x0e")
    disp._write(0xDF, b"\x21\x0c\x02")
    disp._write(0xF0, b"\x45\x09\x08\x08\x26\x2a")
    disp._write(0xF1, b"\x43\x70\x72\x36\x37\x6f")
    disp._write(0xF2, b"\x45\x09\x08\x08\x26\x2a")
    disp._write(0xF3, b"\x43\x70\x72\x36\x37\x6f")
    disp._write(0xED, b"\x1b\x0b")
    disp._write(0xAE, b"\x77")
    disp._write(0xCD, b"\x63")
    disp._write(0x70, b"\x07\x07\x04\x0e\x0f\x09\x07\x08\x03")
    disp._write(0xE8, b"\x34")
    disp._write(0x62, b"\x18\x0d\x71\xed\x70\x70\x18\x0f\x71\xef\x70\x70")
    disp._write(0x63, b"\x18\x11\x71\xf1\x70\x70\x18\x13\x71\xf3\x70\x70")
    disp._write(0x64, b"\x28\x29\xf1\x01\xf1\x00\x07")
    disp._write(0x66, b"\x3c\x00\xcd\x67\x45\x45\x10\x00\x00\x00")
    disp._write(0x67, b"\x00\x3c\x00\x00\x00\x01\x54\x10\x32\x98")
    disp._write(0x74, b"\x10\x85\x80\x00\x00\x4e\x00")
    disp._write(0x98, b"\x3e\x07")
    disp._write(0x35)
    disp._write(0x21)
    disp._write(0x11)
    _sleep_ms(120)
    disp._write(0x29)
    _sleep_ms(20)
    disp.rotation(4)


def reinit_panel(disp: _Gc9a01Display | None) -> None:
    """Re-send GC9A01 register sequence (no RST). Use when a panel blacked out (e.g. shared SPI glitch)."""
    if disp is None:
        return
    try:
        _reinit_gc9a01_registers(disp)
    except Exception as e:
        print(f"  ⚠ Panel reinit failed: {e}")


_HARDWARE_STATUS_FILE = ".furbacca-hardware.json"


def _write_display_status(ok: bool) -> None:
    """Write display init result for nervous_system to read (repo root = cwd when run from wake-furbacca)."""
    try:
        path = os.path.join(os.getcwd(), _HARDWARE_STATUS_FILE)
        with open(path, "w") as f:
            import json as _json

            _json.dump({"displays": "ok" if ok else "fail"}, f)
    except Exception:
        pass


def init_displays(swap_left_right: bool = False) -> tuple[object | None, object | None]:
    """
    Create both displays via gc9a01py (Python owns SPI and DC pin).
    Do not enable the gc9a01 overlay when using this: overlay and Python share DC (GPIO 25)
    and will conflict, causing garbled output.
    Returns (left_eye, right_eye).
    """
    _ = swap_left_right  # reserved for future left/right swap
    _install_compat()

    if os.path.exists("/dev/fb1"):
        print(
            "⚠ /dev/fb1 present (gc9a01 overlay). Disable overlay in config.txt to avoid shared DC (GPIO 25) conflict."
        )

    gc9a01py_lib = os.path.join(_vision_dir, "gc9a01py", "lib")
    if not os.path.isdir(gc9a01py_lib):
        print("⚠ vision/py/gc9a01py/lib not found. Run: bash scripts/setup/fetch-gc9a01py.sh")
        _write_display_status(False)
        return None, None

    sys.path.insert(0, gc9a01py_lib)

    try:
        from .machine_compat.machine import SPI, Pin
    except ImportError:
        sys.path.insert(0, _vision_dir)
        from hardware.machine_compat.machine import SPI, Pin

    baud = int(os.environ.get("SPI_BAUDRATE", "60000000"))  # 60 MHz; higher can cause screen blackout
    spi_left = SPI(0, 0, baudrate=baud)
    spi_right = SPI(0, 1, baudrate=baud)
    dc = Pin(25, Pin.OUT)
    reset = Pin(27, Pin.OUT)
    # BCM 18 is I2S BCLK for MAX98357A — do not use for display backlight or audio breaks until reboot
    backlight = None

    try:
        from gc9a01py import GC9A01  # type: ignore[reportMissingImports]
    except ImportError as e:
        print(f"⚠ Could not import gc9a01py: {e}")
        _write_display_status(False)
        return None, None

    try:
        gc9_ctor = cast(Callable[..., object], GC9A01)
        left_eye: object = gc9_ctor(spi_left, dc=dc, cs=None, reset=reset, backlight=backlight, rotation=4)
        _sleep_ms(20)
        right_eye: object = gc9_ctor(spi_right, dc=dc, cs=None, reset=reset, backlight=None, rotation=4)
        # Both panels share RST: right's init may reset both. Give right time to finish init, then re-init left.
        _sleep_ms(80)
        _reinit_gc9a01_registers(cast(_Gc9a01Display, left_eye))
        _sleep_ms(30)
        backlight_obj = getattr(left_eye, "backlight", None)
        if backlight_obj is not None:
            bl = cast(_BacklightLike, backlight_obj)
            _ = bl.value(1)
        _write_display_status(True)
        return left_eye, right_eye
    except Exception as e:
        print(f"⚠ GC9A01 init failed: {e}")
        import traceback

        traceback.print_exc()
        _write_display_status(False)
        return None, None
