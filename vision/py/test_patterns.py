"""
Test patterns for displays: XY gradient, circular rainbow. No image file; same blit path as eye image.
"""

from __future__ import annotations

import math
from typing import Protocol

from vision.py.assets import config
from vision.py.hardware import blit

EYE_SIZE = config.EYE_SIZE


class DisplayProtocol(Protocol):
    """Minimal display interface: blit_buffer for row-by-row RGB565."""

    def blit_buffer(
        self,
        buf: bytes | bytearray,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> None: ...


def _hsv_to_rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
    """H,S,V in [0,1] -> (r,g,b) 0-255."""
    if s <= 0:
        return (int(v * 255), int(v * 255), int(v * 255))
    h = (h % 1.0) * 6
    i = int(h)
    f = h - i
    p = v * (1 - s)
    q = v * (1 - s * f)
    t = v * (1 - s * (1 - f))
    i %= 6
    if i == 0:
        r, g, b = v, t, p
    elif i == 1:
        r, g, b = q, v, p
    elif i == 2:
        r, g, b = p, v, t
    elif i == 3:
        r, g, b = p, q, v
    elif i == 4:
        r, g, b = t, p, v
    else:
        r, g, b = v, p, q
    return (int(r * 255), int(g * 255), int(b * 255))


def show_gradient(display: DisplayProtocol | None) -> None:
    """Draw XY gradient (red/green sweep) to display."""
    if display is None:
        return
    try:
        row_buf = bytearray(EYE_SIZE * 2)
        for y in range(EYE_SIZE):
            for x in range(EYE_SIZE):
                r = x * 255 // (EYE_SIZE - 1) if EYE_SIZE > 1 else 0
                g = y * 255 // (EYE_SIZE - 1) if EYE_SIZE > 1 else 0
                b = 128
                row_buf[x * 2 : x * 2 + 2] = blit.rgb565(r, g, b)
            display.blit_buffer(row_buf, 0, y, EYE_SIZE, 1)
    except Exception as e:
        print(f"⚠ Gradient error: {e}")


def show_rainbow(display: DisplayProtocol | None) -> None:
    """Draw circular rainbow (hue by angle from center) to display."""
    if display is None:
        return
    try:
        cx = (EYE_SIZE - 1) / 2.0
        cy = (EYE_SIZE - 1) / 2.0
        row_buf = bytearray(EYE_SIZE * 2)
        for y in range(EYE_SIZE):
            for x in range(EYE_SIZE):
                dx, dy = x - cx, y - cy
                angle = math.atan2(dy, dx)
                hue = (angle / (2 * math.pi) + 0.5) % 1.0
                r, g, b = _hsv_to_rgb(hue, 1.0, 1.0)
                row_buf[x * 2 : x * 2 + 2] = blit.rgb565(r, g, b)
            display.blit_buffer(row_buf, 0, y, EYE_SIZE, 1)
    except Exception as e:
        print(f"⚠ Rainbow error: {e}")
