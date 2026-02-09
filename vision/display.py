"""
Initialize dual GC9A01 displays using russhughes/gc9a01py and machine_compat (CPython on Raspberry Pi).
Pinout from vision/config.h: DC=25, RST=27, CS_L=8 (spidev0.0), CS_R=7 (spidev0.1), BL=18.
"""
import sys
import time
import os

_vision_dir = os.path.dirname(os.path.abspath(__file__))

# Inject MicroPython compat before importing gc9a01py
def _install_compat():
    # micropython.const
    import types
    micropython = types.ModuleType("micropython")
    micropython.const = lambda x: x
    sys.modules["micropython"] = micropython
    # ustruct
    sys.modules["ustruct"] = __import__("struct")
    # time.sleep_ms
    _sleep = time.sleep
    time.sleep_ms = lambda ms: _sleep(ms / 1000.0)


def init_displays(swap_left_right=False):
    """
    Create both displays via gc9a01py (Python owns SPI and DC pin).
    Do not enable the gc9a01 overlay when using this: overlay and Python share DC (GPIO 25)
    and will conflict, causing garbled output.
    Returns (left_eye, right_eye).
    """
    _install_compat()

    if os.path.exists("/dev/fb1"):
        print("⚠ /dev/fb1 present (gc9a01 overlay). Disable overlay in config.txt to avoid shared DC (GPIO 25) conflict.")

    gc9a01py_lib = os.path.join(_vision_dir, "gc9a01py", "lib")
    if not os.path.isdir(gc9a01py_lib):
        print("⚠ vision/gc9a01py/lib not found. Run: bash scripts/fetch-gc9a01py.sh")
        return None, None

    sys.path.insert(0, gc9a01py_lib)

    try:
        from machine_compat.machine import SPI, Pin
    except ImportError:
        sys.path.insert(0, _vision_dir)
        from machine_compat.machine import SPI, Pin

    # Lower baudrate helps with long jumper wires (snow/static from signal integrity). Default 4 MHz; set SPI_BAUDRATE env for override (e.g. 2000000).
    _baud = int(os.environ.get("SPI_BAUDRATE", "4000000"))
    spi_left = SPI(0, 0, baudrate=_baud)
    spi_right = SPI(0, 1, baudrate=_baud)
    dc = Pin(25, Pin.OUT)
    reset = Pin(27, Pin.OUT)
    backlight = Pin(18, Pin.OUT)

    try:
        from gc9a01py import GC9A01
    except ImportError as e:
        print(f"⚠ Could not import gc9a01py: {e}")
        return None, None

    try:
        left_eye = GC9A01(spi_left, dc=dc, cs=None, reset=reset, backlight=backlight, rotation=4)
        time.sleep_ms(20)
        right_eye = GC9A01(spi_right, dc=dc, cs=None, reset=reset, backlight=None, rotation=4)
        # Right's init did hard_reset() and reset both panels; left was left in power-on state. Re-init left (no reset to avoid resetting right again).
        left_eye.reinit(do_reset=False)
        print("✅ Hardware: gc9a01py displays ready (left, right).")
        return left_eye, right_eye
    except Exception as e:
        print(f"⚠ GC9A01 init failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None
