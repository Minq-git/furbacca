"""
Optimized Eye Shapes: NumPy-native masking without PIL.
Vectorized implementations for Heart, Gemini, Stern, Sus, and more.
Orientation corrected for 180-degree display flip.
"""

from __future__ import annotations

import math
from typing import cast

import numpy as np
from numpy.typing import NDArray

_F32 = NDArray[np.float32]
_Bool = NDArray[np.bool_]

# Cache for NumPy boolean masks: (shape_name, size, mirror) -> bool array
_mask_cache_np: dict[tuple[str, int, bool], NDArray[np.bool_]] = {}


def get_shape_mask_numpy(shape_name: str | None, size: int, mirror: bool = False) -> NDArray[np.bool_]:
    """
    Returns a boolean NumPy mask: True inside the shape, False outside.
    Algebraic vectorized implementation for high-speed masking.
    """
    shape_name = (shape_name or "round").strip().lower()
    key = (shape_name, size, mirror)

    if key in _mask_cache_np:
        return _mask_cache_np[key]

    # Create coordinate grid
    grid = cast(_F32, np.indices((size, size), dtype=np.float32))
    y_idx: _F32 = cast(_F32, grid[0])
    x_idx: _F32 = cast(_F32, grid[1])
    cx: float = size / 2.0
    cy: float = size / 2.0
    mask: _Bool = cast(_Bool, np.zeros((size, size), dtype=np.bool_))

    # --- Standard Shapes ---
    if shape_name == "round":
        mask = cast(_Bool, (x_idx - cx) ** 2 + (y_idx - cy) ** 2 <= (size / 2.0) ** 2)

    elif shape_name == "bean":
        w, h = size * 0.45, size * 0.25
        bend = size * 0.20
        x_off = cast(_F32, x_idx - cx)
        y_off = cast(_F32, y_idx - cy + bend * (x_off / w) ** 2)
        mask = cast(_Bool, (x_off / w) ** 2 + (y_off / h) ** 2 <= 1.0)

    elif shape_name == "dome":
        # Array bottom is display top -> display-arched top = y_idx >= cy
        dist = cast(_Bool, (x_idx - cx) ** 2 + (y_idx - cy) ** 2 <= (size / 2.0) ** 2)
        mask = cast(_Bool, dist & cast(_Bool, y_idx >= cy))

    elif shape_name == "half_moon":
        # Array top is display bottom -> display-rounded bottom = y_idx <= cy
        dist = cast(_Bool, (x_idx - cx) ** 2 + (y_idx - cy) ** 2 <= (size / 2.0) ** 2)
        mask = cast(_Bool, dist & cast(_Bool, y_idx <= cy))

    elif shape_name == "oval":
        ry = (size / 2.0) * 0.84
        mask = cast(
            _Bool,
            (x_idx - cx) ** 2 / (size / 2.0) ** 2 + (y_idx - cy) ** 2 / ry**2 <= 1.0,
        )

    elif shape_name == "pill":
        rx, ry = (size / 2.0) * 0.64, (size / 2.0) * 0.90
        mask = cast(_Bool, (x_idx - cx) ** 2 / rx**2 + (y_idx - cy) ** 2 / ry**2 <= 1.0)

    elif shape_name == "tilted":
        angle = math.radians(-18)
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        rx, ry = size / 2.0, (size / 2.0) * 0.84
        xr = cast(_F32, (x_idx - cx) * cos_a - (y_idx - cy) * sin_a)
        yr = cast(_F32, (x_idx - cx) * sin_a + (y_idx - cy) * cos_a)
        mask = cast(_Bool, (xr**2 / rx**2) + (yr**2 / ry**2) <= 1.0)

    # --- Complex Shapes ---
    elif shape_name == "anime":
        # Flat display-top, rounded bottom; 180 flip + left-right flip so inner corner correct
        x_local: _F32 = cast(_F32, (cx - x_idx) / (size * 0.45))  # flip x so anime eye not inverted
        y_local: _F32 = cast(_F32, (y_idx - cy) / (size * 0.35))
        mask = cast(
            _Bool,
            cast(_Bool, x_local**2 + y_local**2 <= 1.0)
            & cast(_Bool, y_idx >= cy * 0.6)
            & cast(_Bool, x_idx >= cx * 0.6),
        )

    elif shape_name == "glare":
        # Flat display-top, deep rounded bottom (180 flip: flat at high y in array = display top)
        dist = cast(
            _Bool,
            (x_idx - cx) ** 2 / (size * 0.5) ** 2 + (y_idx - cy) ** 2 / (size * 0.35) ** 2 <= 1.0,
        )
        mask = cast(_Bool, dist & cast(_Bool, y_idx <= cy * 1.3))

    elif shape_name == "gemini":
        # 4-pointed star (Astroid curve)
        scale = size * 0.45
        x_ast: _F32 = cast(_F32, np.abs((x_idx - cx) / scale))
        y_ast: _F32 = cast(_F32, np.abs((y_idx - cy) / scale))
        mask = cast(_Bool, (x_ast**0.66 + y_ast**0.66) <= 1.0)

    elif shape_name == "heart":
        # Generic heart shape, fit within safe-zone
        scale = size * 0.35
        x: _F32 = cast(_F32, (x_idx - cx) / scale)
        y: _F32 = cast(_F32, (y_idx - cy) / scale + 0.25)  # Point-down correction for 180 flip
        mask = cast(_Bool, (x**2 + y**2 - 1) ** 3 - x**2 * y**3 <= 0)

    elif shape_name == "sharp":
        # Cat-eye shape
        lx, ly = 0.10 * size, 0.75 * size
        rx, ry = 0.95 * size, 0.35 * size
        ty = -0.15 * size
        by = 1.05 * size
        within_x: _Bool = cast(_Bool, (x_idx >= lx) & (x_idx <= rx))
        t: _F32 = cast(_F32, np.clip((x_idx - lx) / (rx - lx), 0.0, 1.0))
        y_top: _F32 = cast(_F32, (1 - t) ** 2 * ly + 2 * (1 - t) * t * ty + t**2 * ry)
        y_bottom: _F32 = cast(_F32, (1 - t) ** 2 * ly + 2 * (1 - t) * t * by + t**2 * ry)
        mask = cast(_Bool, within_x & cast(_Bool, y_idx >= y_top) & cast(_Bool, y_idx <= y_bottom))

    elif shape_name == "sus":
        # Squashed, outer-tilted oval
        angle = math.radians(15)
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        xr = cast(_F32, (x_idx - cx) * cos_a - (y_idx - cy) * sin_a)
        yr = cast(_F32, (x_idx - cx) * sin_a + (y_idx - cy) * cos_a)
        mask = cast(_Bool, (xr**2 / (size * 0.45) ** 2) + (yr**2 / (size * 0.18) ** 2) <= 1.0)

    elif shape_name == "stern":
        # Heavy inner-brow tilt (180 flip + left-right flip)
        x_off = cast(_F32, cx - x_idx)  # mirror x
        dist = cast(
            _Bool,
            x_off**2 / (size * 0.45) ** 2 + (y_idx - cy) ** 2 / (size * 0.35) ** 2 <= 1.0,
        )
        mask = cast(_Bool, dist & cast(_Bool, x_off - (y_idx - cy) * 1.5 >= -size * 0.2))

    elif shape_name == "concern":
        # Same as stern but inverse x (brow on other side)
        x_off = cast(_F32, x_idx - cx)
        dist = cast(
            _Bool,
            x_off**2 / (size * 0.45) ** 2 + (y_idx - cy) ** 2 / (size * 0.35) ** 2 <= 1.0,
        )
        mask = cast(_Bool, dist & cast(_Bool, x_off - (y_idx - cy) * 1.5 >= -size * 0.2))

    elif shape_name == "kawaii":
        # Tall rounded display-top, flat display-bottom (180 flip: flat at low y in array)
        dist = cast(
            _Bool,
            (x_idx - cx) ** 2 / (size * 0.38) ** 2 + (y_idx - cy) ** 2 / (size * 0.45) ** 2 <= 1.0,
        )
        mask = cast(_Bool, dist & cast(_Bool, y_idx >= cy * 0.7))

    else:
        # Unknown shape: fall back to round so we never ship an all-False mask (no black eye)
        mask = cast(_Bool, (x_idx - cx) ** 2 + (y_idx - cy) ** 2 <= (size / 2.0) ** 2)

    if mirror:
        mask = cast(_Bool, np.flip(mask, axis=1))

    _mask_cache_np[key] = mask
    return mask


def apply_shape_mask_numpy(
    frame_arr: NDArray[np.uint8] | None, shape_name: str | None = None, mirror: bool = False
) -> NDArray[np.uint8] | None:
    if frame_arr is None:
        return None
    size = frame_arr.shape[0]
    mask = get_shape_mask_numpy(shape_name, size, mirror=mirror)
    frame_arr[~mask] = 0
    return frame_arr


def get_blink_line(shape_name: str | None, size: int) -> tuple[tuple[int, int], tuple[int, int]]:
    """
    Return ((x0, y0), (x1, y1)) for the closed-eye blink line.
    Coordinates match display-orientation (corrected for 180 flip).
    """
    shape_name = (shape_name or "round").strip().lower()
    cy = size // 2

    # Standard horizontal blink
    if shape_name in (
        "round",
        "oval",
        "pill",
        "half_moon",
        "bean",
        "dome",
        "heart",
        "gemini",
        "kawaii",
        "glare",
        "anime",
    ):
        return ((0, cy), (size, cy))

    if shape_name == "sharp":
        return ((int(size * 0.10), int(size * 0.75)), (int(size * 0.95), int(size * 0.35)))

    if shape_name == "sus":
        # Slant follows the squashed 15-degree tilt
        tan15 = math.tan(math.radians(15))
        offset = int((size / 2) * tan15)
        return ((0, cy - offset), (size, cy + offset))

    if shape_name in ("stern", "concern"):
        # Slant follows the heavy brow cut
        return ((int(size * 0.05), int(size * 0.4)), (int(size * 0.95), int(size * 0.8)))

    if shape_name == "tilted":
        tan18 = math.tan(math.radians(18))
        offset = int((size / 2) * tan18)
        return ((0, cy - offset), (size, cy + offset))

    return ((0, cy), (size, cy))
