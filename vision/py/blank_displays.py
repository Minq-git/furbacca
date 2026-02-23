"""Blank both GC9A01 displays (best-effort).

Run from repo root:
  python3 -m vision.py.blank_displays
"""

from __future__ import annotations

from vision.py.assets import config
from vision.py.hardware import blit, display


def main() -> None:
    left, right = display.init_displays(swap_left_right=config.SWAP_LEFT_RIGHT_SPI)
    if left is None and right is None:
        return
    try:
        from PIL import Image
    except Exception:
        return

    size = int(getattr(config, "EYE_SIZE", 240))
    img = Image.new("RGB", (size, size), (0, 0, 0))
    blit.blit_pil_to_both(
        left,
        right,
        img,
        img,
        reverse_rows=False,
        outside_in=False,
        inside_out=False,
        partial_rows=None,
    )


if __name__ == "__main__":
    main()
