"""
Optimized Render: NumPy-first pipeline with vectorized spherical sampling.
Source of truth is NumPy; PIL is only used for asset loading and final output.
"""
import math
import numpy as np
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    Image = None

import config
import assets
import shapes

# Internal caches
_texture_arrays = {}           # eye_type -> {'sclera': arr, 'iris': arr}
_gaze_cache_numpy = {}         # (eye_type, qx, qy) -> NumPy array (uint8)
_blink_overlay_cache = {}      # (shape, mirror) -> PIL image

def _get_textures_numpy(eye_type):
    """Retrieve or load eye textures as NumPy arrays."""
    if eye_type not in _texture_arrays:
        s_img = assets.load_sclera_image(eye_type)
        i_img = assets.load_iris_image(eye_type)
        _texture_arrays[eye_type] = {
            'sclera': np.array(s_img) if s_img else None,
            'iris': np.array(i_img) if i_img else None
        }
    return _texture_arrays[eye_type]

def _sample_texture_spherical_numpy(tex_arr, cx, cy, r_max, out_shape, invert_v=False):
    """
    Vectorized spherical sampling using NumPy indexing.
    Returns (sx, sy) index arrays and a validity mask.
    """
    h_out, w_out = out_shape
    h_tex, w_tex = tex_arr.shape[:2]

    # 1. Create coordinate grid for the output image
    y_idx, x_idx = np.indices((h_out, w_out), dtype=np.float32)
    
    # 2. Distance and angle relative to the center of the gaze (pole)
    dx = x_idx - cx
    dy = y_idx - cy
    r = np.sqrt(dx*dx + dy*dy)
    mask = r <= r_max
    
    # 3. Calculate mapping (atan2 and r/r_max)
    angle = np.arctan2(dy, dx)
    u = (angle + np.pi) / (2.0 * np.pi)
    v = r / r_max
    
    # 4. Map to texture pixel indices
    sx = ((u * (w_tex - 1)) + 0.5).astype(np.int32) % w_tex
    if invert_v:
        sy = ((v * (h_tex - 1)) + 0.5).astype(np.int32)
    else:
        sy = (((1.0 - v) * (h_tex - 1)) + 0.5).astype(np.int32)
    
    sy = np.clip(sy, 0, h_tex - 1)
    return sx, sy, mask

def build_eye_base_sclera_iris_at_center(pole_x, pole_y, eye_type=None, size=None):
    """Builds the eyeball (sclera + iris) as a NumPy array."""
    eye_type = eye_type or config.get_eye_type()
    size = size or config.EYE_SIZE
    
    textures = _get_textures_numpy(eye_type)
    sclera_arr = textures['sclera']
    iris_arr = textures['iris']
    
    if sclera_arr is None:
        return np.zeros((size, size, 3), dtype=np.uint8)

    invert_v, iris_scale, sclera_scale = config.eye_type_scales(eye_type)
    scale = size / config.EYE_SIZE
    
    # Scaled dimensions
    px_s, py_s = pole_x * scale, pole_y * scale
    R_eye = (size // 2) * config.EYE_LAYER_VIEWPORT_SCALE * sclera_scale
    R_iris = config.IRIS_R * iris_scale * config.EYE_LAYER_VIEWPORT_SCALE * scale
    
    # Render Sclera
    out_arr = np.zeros((size, size, 3), dtype=np.uint8)
    sx, sy, mask = _sample_texture_spherical_numpy(sclera_arr, px_s, py_s, R_eye, (size, size), invert_v)
    out_arr[mask] = sclera_arr[sy[mask], sx[mask]]
    
    # Render Iris
    if iris_arr is not None:
        isx, isy, imask = _sample_texture_spherical_numpy(iris_arr, px_s, py_s, R_iris, (size, size), invert_v)
        out_arr[imask] = iris_arr[isy[imask], isx[imask]]
        
    return out_arr

def build_eye_base_sclera_iris():
    """
    Bridge function for initialization checks in eyes.py.
    Returns the eyeball at the default center (EYE_SIZE // 2) as a PIL image.
    """
    center = config.EYE_SIZE // 2
    # Call the new centered NumPy function
    arr = build_eye_base_sclera_iris_at_center(center, center)
    if arr is None:
        return None
    # Convert to PIL so eyes.py can validate HAS_PIL and basic rendering
    return Image.fromarray(arr)

def _get_eye_base_cached_numpy(px, py, force_type=None):
    """Retrieves quantized gaze base from cache as a NumPy array."""
    cx, cy = config.EYE_SIZE // 2, config.EYE_SIZE // 2
    step = config.EYE_GAZE_CACHE_STEP
    
    qx_idx = round(((px - cx) / 35.0) / step)
    qy_idx = round(((py - cy) / 35.0) / step)
    
    # Use forced type for pre-loading, otherwise use current config
    eye_type = force_type if force_type else config.get_eye_type()
    key = (eye_type, qx_idx, qy_idx)
    
    if key not in _gaze_cache_numpy:
        qpx = int(cx + (qx_idx * step) * 35)
        qpy = int(cy + (qy_idx * step) * 35)
        _gaze_cache_numpy[key] = build_eye_base_sclera_iris_at_center(qpx, qpy, eye_type=eye_type, size=config.EYE_BUILD_SIZE)
        
    return _gaze_cache_numpy[key].copy()

def _draw_pupil_numpy(base_arr, px, py, r, eye_type):
    """Vectorized pupil mask."""
    h, w = base_arr.shape[:2]
    y_grid, x_grid = np.ogrid[:h, :w]
    if eye_type == "dragon":
        mask = (np.abs(x_grid - px) / max(2.0, r * 0.35)) + (np.abs(y_grid - py) / r) <= 1.0
    else:
        mask = (x_grid - px) ** 2 + (y_grid - py) ** 2 <= r ** 2
    base_arr[mask] = 0

def render_blink_overlay(mirror=False):
    """
    Blink layer: black + eyelid line following the eye shape.
    Cached per (shape, mirror) for performance.
    """
    if not HAS_PIL:
        return None
        
    from PIL import ImageDraw
    shape_name = (config.get_eye_shape() or "round").strip().lower()
    size = config.EYE_SIZE
    key = (shape_name, mirror)
    
    if key in _blink_overlay_cache:
        return _blink_overlay_cache[key]
        
    # Create the blink overlay (eyelid)
    overlay = Image.new("RGB", (size, size), (0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Get the specific blink line coordinates from shapes.py
    line_coords = shapes.get_blink_line(shape_name, size)
    if line_coords:
        (x0, y0), (x1, y1) = line_coords
        draw.line([(x0, y0), (x1, y1)], fill=(28, 28, 28), width=3)
    
    if mirror:
        overlay = overlay.transpose(Image.FLIP_LEFT_RIGHT)
        
    _blink_overlay_cache[key] = overlay
    return overlay

def render_animated_frame(cached_eye_base_240, pupil_x, pupil_y, blink_state="open", pupil_radius=None):
    """Final render: Everything is NumPy until the final PIL conversion for the UI/shapes stack."""
    cx, cy = config.EYE_SIZE // 2, config.EYE_SIZE // 2
    eye_type = config.get_eye_type()
    
    # 1. Physics & Coordinates
    r = max(8.0, min(60.0, float(pupil_radius or config.eye_type_pupil_radii(eye_type)[0])))
    px, py = int(cx + pupil_x * 35), int(cy + pupil_y * 35)
    
    # 2. Get the base eyeball (Sclera + Iris) from NumPy cache
    base_arr = _get_eye_base_cached_numpy(px, py)
    
    # 3. Draw Pupil directly in NumPy
    scale_build = config.EYE_BUILD_SIZE / config.EYE_SIZE
    _draw_pupil_numpy(base_arr, px * scale_build, py * scale_build, r * scale_build, eye_type)
    
    # 4. Final conversion to PIL only for compatibility with the blit/shape pipeline
    result = Image.fromarray(base_arr)
    
    if config.EYE_BUILD_SIZE != config.EYE_SIZE:
        resample = getattr(Image, "Resampling", Image).LANCZOS
        result = result.resize((config.EYE_SIZE, config.EYE_SIZE), resample)
        
    return result

def preload_all_types():
    """
    Pre-loads textures and initial gaze mappings for all eye types.
    Run this at startup to ensure switching is instantaneous.
    """
    print("  Pre-loading eye textures...")
    # These match the types supported by assets.py
    eye_types = ["default", "human", "dragon", "demon"] 
    
    center = config.EYE_SIZE // 2
    
    for etype in eye_types:
        print(f"    - Loading: {etype}")
        # 1. Populate texture cache
        _get_textures_numpy(etype)
        
        # 2. Populate initial centered gaze cache
        # This triggers the expensive spherical sampling once per type
        _get_eye_base_cached_numpy(center, center, force_type=etype)