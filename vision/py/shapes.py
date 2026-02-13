"""
Optimized Eye Shapes: NumPy-native masking without PIL.
Uses vectorized math for ellipses, polygons, and Bezier curves.
"""
import numpy as np
import math
import config

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

    if shape_name == "round":
        mask = (x_idx - cx)**2 + (y_idx - cy)**2 <= (size/2.0)**2
        
    elif shape_name == "oval":
        # Standard oval (horizontal ellipse)
        ry = (size / 2.0) * 0.84
        mask = (x_idx - cx)**2 / (size/2.0)**2 + (y_idx - cy)**2 / ry**2 <= 1.0

    elif shape_name == "pill":
        # Tall and narrow ellipse
        rx, ry = (size/2.0) * 0.64, (size/2.0) * 0.90
        mask = (x_idx - cx)**2 / rx**2 + (y_idx - cy)**2 / ry**2 <= 1.0

    elif shape_name == "sharp":
        # Vectorized Quadratic Bezier implementation for "Cat Eye"
        lx, ly = 0.10 * size, 0.75 * size  # Inner corner (lower)
        rx, ry = 0.95 * size, 0.35 * size  # Outer corner (higher)
        tx, ty = 0.25 * size, -0.15 * size # Top lid control point
        bx, by = 0.50 * size, 1.05 * size  # Bottom lid control point
        
        within_x = (x_idx >= lx) & (x_idx <= rx)
        # Map x to t [0, 1] for Bezier calculation
        t = np.clip((x_idx - lx) / (rx - lx), 0, 1)
        
        # Quadratic Bezier: (1-t)^2*P0 + 2(1-t)t*P1 + t^2*P2
        y_top = (1-t)**2 * ly + 2*(1-t)*t * ty + t**2 * ry
        y_bottom = (1-t)**2 * ly + 2*(1-t)*t * by + t**2 * ry
        mask = within_x & (y_idx >= y_top) & (y_idx <= y_bottom)

    elif shape_name == "bean":
        # Kidney shape: horizontal ellipse with a parabolic y-bend
        w, h = size * 0.45, size * 0.25
        bend = size * 0.20
        x_off = x_idx - cx
        # Apply the upward bend (smile curve) to the y-coordinate
        y_off = y_idx - cy + bend * (x_off / w)**2
        mask = (x_off / w)**2 + (y_off / h)**2 <= 1.0

    elif shape_name == "tilted":
        # Oval rotated -18 degrees (inner corner lower)
        angle = math.radians(-18)
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        rx, ry = size/2.0, (size/2.0) * 0.84
        # Apply rotation matrix
        xr = (x_idx - cx) * cos_a - (y_idx - cy) * sin_a
        yr = (x_idx - cx) * sin_a + (y_idx - cy) * cos_a
        mask = (xr**2 / rx**2) + (yr**2 / ry**2) <= 1.0

    elif shape_name == "dome":
        # Arched top, flat bottom (y <= cy)
        dist = (x_idx - cx)**2 + (y_idx - cy)**2 <= (size/2.0)**2
        mask = dist & (y_idx >= cy)
        
    elif shape_name == "half_moon":
        # Rounded bottom, flat top (y >= cy)
        dist = (x_idx - cx)**2 + (y_idx - cy)**2 <= (size/2.0)**2
        mask = dist & (y_idx <= cy)

    elif shape_name == "trapezoid":
        # Angular straight lines; top wider than bottom (approximated)
        mask = (x_idx >= size*0.18) & (x_idx <= size*0.82) & \
               (y_idx >= size*0.18) & (y_idx <= size*0.82)

    if mirror:
        mask = np.flip(mask, axis=1)

    _mask_cache_np[key] = mask
    return mask

def _generate_complex_mask(shape_name, size):
    """Helper to generate polygon-based masks for complex shapes."""
    # We use a simple path-filling logic for sharp/bean
    mask = np.zeros((size, size), dtype=bool)
    # [Note: For complex Beziers without PIL, you can use a simplified 
    # algebraic distance check or pre-render a small LUT]
    # For now, we default to 'round' to prevent crashes during dev
    y, x = np.ogrid[:size, :size]
    return (x - size/2)**2 + (y - size/2)**2 <= (size/2)**2

def apply_shape_mask_numpy(frame_arr, shape_name=None, mirror=False):
    """
    Applies the mask directly to a NumPy array (H, W, 3).
    """
    if frame_arr is None: return None
    size = frame_arr.shape[0]
    mask = get_shape_mask_numpy(shape_name, size, mirror=mirror)
    
    # Vectorized 'zero out' pixels outside the mask
    frame_arr[~mask] = 0
    return frame_arr

def get_blink_line(shape_name, size):
    # Keep your existing logic for the blink line coordinates
    shape_name = (shape_name or "round").strip().lower()
    cy = size // 2
    if shape_name == "sharp":
        return ((int(size * 0.10), int(size * 0.75)), (int(size * 0.95), int(size * 0.35)))
    return ((0, cy), (size, cy))