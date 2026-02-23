"""
Optimized Eye Shapes: NumPy-native masking without PIL.
Vectorized implementations for Heart, Gemini, Stern, Sus, and more.
Orientation corrected for 180-degree display flip.
"""
import math

import numpy as np

# Cache for NumPy boolean masks: (shape_name, size, mirror) -> bool array
_mask_cache_np = {}

def get_shape_mask_numpy(shape_name, size, mirror=False):
    """
    Returns a boolean NumPy mask: True inside the shape, False outside.
    Algebraic vectorized implementation for high-speed masking.
    """
    shape_name = (shape_name or "round").strip().lower()
    key = (shape_name, size, mirror)

    if key in _mask_cache_np:
        return _mask_cache_np[key]

    # Create coordinate grid
    y_idx, x_idx = np.indices((size, size), dtype=np.float32)
    cx, cy = size / 2.0, size / 2.0
    mask = np.zeros((size, size), dtype=bool)

    # --- Standard Shapes ---
    if shape_name == "round":
        mask = (x_idx - cx)**2 + (y_idx - cy)**2 <= (size/2.0)**2

    elif shape_name == "bean":
        w, h = size * 0.45, size * 0.25
        bend = size * 0.20
        x_off = x_idx - cx
        y_off = y_idx - cy + bend * (x_off / w)**2
        mask = (x_off / w)**2 + (y_off / h)**2 <= 1.0

    elif shape_name == "dome":
        # Array bottom is display top -> display-arched top = y_idx >= cy
        dist = (x_idx - cx)**2 + (y_idx - cy)**2 <= (size/2.0)**2
        mask = dist & (y_idx >= cy)

    elif shape_name == "half_moon":
        # Array top is display bottom -> display-rounded bottom = y_idx <= cy
        dist = (x_idx - cx)**2 + (y_idx - cy)**2 <= (size/2.0)**2
        mask = dist & (y_idx <= cy)

    elif shape_name == "oval":
        ry = (size / 2.0) * 0.84
        mask = (x_idx - cx)**2 / (size/2.0)**2 + (y_idx - cy)**2 / ry**2 <= 1.0

    elif shape_name == "pill":
        rx, ry = (size/2.0) * 0.64, (size/2.0) * 0.90
        mask = (x_idx - cx)**2 / rx**2 + (y_idx - cy)**2 / ry**2 <= 1.0

    elif shape_name == "tilted":
        angle = math.radians(-18)
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        rx, ry = size/2.0, (size/2.0) * 0.84
        xr = (x_idx - cx) * cos_a - (y_idx - cy) * sin_a
        yr = (x_idx - cx) * sin_a + (y_idx - cy) * cos_a
        mask = (xr**2 / rx**2) + (yr**2 / ry**2) <= 1.0

    # --- Complex Shapes ---
    elif shape_name == "anime":
        # Flat display-top, rounded bottom; 180 flip + left-right flip so inner corner correct
        x_local = (cx - x_idx) / (size * 0.45)  # flip x so anime eye not inverted
        y_local = (y_idx - cy) / (size * 0.35)
        mask = (x_local**2 + y_local**2 <= 1.0) & (y_idx >= cy * 0.6) & (x_idx >= cx * 0.6)

    elif shape_name == "glare":
        # Flat display-top, deep rounded bottom (180 flip: flat at high y in array = display top)
        dist = (x_idx - cx)**2 / (size*0.5)**2 + (y_idx - cy)**2 / (size*0.35)**2 <= 1.0
        mask = dist & (y_idx <= cy * 1.3)

    elif shape_name == "gemini":
        # 4-pointed star (Astroid curve)
        scale = size * 0.45
        x_ast = np.abs((x_idx - cx) / scale)
        y_ast = np.abs((y_idx - cy) / scale)
        mask = (x_ast**0.66 + y_ast**0.66) <= 1.0

    elif shape_name == "heart":
        # Generic heart shape, fit within safe-zone
        scale = size * 0.35
        x = (x_idx - cx) / scale
        y = (y_idx - cy) / scale + 0.25 # Point-down correction for 180 flip
        mask = (x**2 + y**2 - 1)**3 - x**2 * y**3 <= 0

    elif shape_name == "sharp":
        # Cat-eye shape
        lx, ly = 0.10 * size, 0.75 * size
        rx, ry = 0.95 * size, 0.35 * size
        ty = -0.15 * size
        by = 1.05 * size
        within_x = (x_idx >= lx) & (x_idx <= rx)
        t = np.clip((x_idx - lx) / (rx - lx), 0, 1)
        y_top = (1-t)**2 * ly + 2*(1-t)*t * ty + t**2 * ry
        y_bottom = (1-t)**2 * ly + 2*(1-t)*t * by + t**2 * ry
        mask = within_x & (y_idx >= y_top) & (y_idx <= y_bottom)

    elif shape_name == "sus":
        # Squashed, outer-tilted oval
        angle = math.radians(15)
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        xr = (x_idx - cx) * cos_a - (y_idx - cy) * sin_a
        yr = (x_idx - cx) * sin_a + (y_idx - cy) * cos_a
        mask = (xr**2 / (size*0.45)**2) + (yr**2 / (size*0.18)**2) <= 1.0

    elif shape_name == "stern":
        # Heavy inner-brow tilt (180 flip + left-right flip)
        x_off = cx - x_idx  # mirror x
        dist = x_off**2 / (size*0.45)**2 + (y_idx - cy)**2 / (size*0.35)**2 <= 1.0
        mask = dist & (x_off - (y_idx - cy) * 1.5 >= -size * 0.2)

    elif shape_name == "concern":
        # Same as stern but inverse x (brow on other side)
        x_off = x_idx - cx
        dist = x_off**2 / (size*0.45)**2 + (y_idx - cy)**2 / (size*0.35)**2 <= 1.0
        mask = dist & (x_off - (y_idx - cy) * 1.5 >= -size * 0.2)

    elif shape_name == "kawaii":
        # Tall rounded display-top, flat display-bottom (180 flip: flat at low y in array)
        dist = (x_idx - cx)**2 / (size*0.38)**2 + (y_idx - cy)**2 / (size*0.45)**2 <= 1.0
        mask = dist & (y_idx >= cy * 0.7)

    else:
        # Unknown shape: fall back to round so we never ship an all-False mask (no black eye)
        mask = (x_idx - cx) ** 2 + (y_idx - cy) ** 2 <= (size / 2.0) ** 2

    if mirror:
        mask = np.flip(mask, axis=1)

    _mask_cache_np[key] = mask
    return mask

def apply_shape_mask_numpy(frame_arr, shape_name=None, mirror=False):
    if frame_arr is None:
        return None
    size = frame_arr.shape[0]
    mask = get_shape_mask_numpy(shape_name, size, mirror=mirror)
    frame_arr[~mask] = 0
    return frame_arr

def get_blink_line(shape_name, size):
    """
    Return ((x0, y0), (x1, y1)) for the closed-eye blink line.
    Coordinates match display-orientation (corrected for 180 flip).
    """
    shape_name = (shape_name or "round").strip().lower()
    cy = size // 2

    # Standard horizontal blink
    if shape_name in ("round", "oval", "pill", "half_moon", "bean", "dome", "heart", "gemini", "kawaii", "glare", "anime"):
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
