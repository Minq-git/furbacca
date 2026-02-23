"""
Optimized Render: NumPy-first pipeline with vectorized spherical sampling.
Source of truth is NumPy; PIL is only used for asset loading and final output.
"""

from __future__ import annotations

import math

import numpy as np

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    Image = None  # type: ignore[misc, assignment]

from assets import config, loaders

from engine import shapes

# Internal caches
_texture_arrays: dict[str, dict[str, np.ndarray | None]] = {}
_gaze_cache_numpy: dict[tuple[str, int, int], np.ndarray] = {}
_blink_overlay_cache: dict[tuple[str, bool], object] = {}


def _get_textures_numpy(eye_type: str) -> dict[str, np.ndarray | None]:
    """Retrieve or load eye textures as NumPy arrays."""
    if eye_type not in _texture_arrays:
        s_img = loaders.load_sclera_image(eye_type)
        i_img = loaders.load_iris_image(eye_type)
        _texture_arrays[eye_type] = {
            "sclera": np.array(s_img) if s_img else None,
            "iris": np.array(i_img) if i_img else None,
        }
    return _texture_arrays[eye_type]


def _sample_texture_spherical_numpy(
    tex_arr: np.ndarray,
    cx: float,
    cy: float,
    r_max: float,
    out_shape: tuple[int, int],
    invert_v: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
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
    r = np.sqrt(dx * dx + dy * dy)
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


def build_eye_base_sclera_iris_at_center(
    pole_x: float,
    pole_y: float,
    eye_type: str | None = None,
    size: int | None = None,
) -> np.ndarray:
    """Builds the eyeball (sclera + iris) as a NumPy array."""
    eye_type = eye_type or config.get_eye_type()
    size = size or config.EYE_SIZE

    textures = _get_textures_numpy(eye_type)
    sclera_arr = textures["sclera"]
    iris_arr = textures["iris"]

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


def build_eye_base_sclera_iris() -> object | None:
    """
    Bridge function for initialization checks in main_eyes.py.
    Returns the eyeball at the default center (EYE_SIZE // 2) as a PIL image.
    """
    center = config.EYE_SIZE // 2
    # Call the new centered NumPy function
    arr = build_eye_base_sclera_iris_at_center(center, center)
    if arr is None:
        return None
    # Convert to PIL so main_eyes.py can validate HAS_PIL and basic rendering
    return Image.fromarray(arr)


def _get_eye_base_cached_numpy(px: int, py: int, force_type: str | None = None) -> np.ndarray:
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
        _gaze_cache_numpy[key] = build_eye_base_sclera_iris_at_center(
            qpx, qpy, eye_type=eye_type, size=config.EYE_BUILD_SIZE
        )

    return _gaze_cache_numpy[key].copy()


def _draw_pupil_numpy(base_arr: np.ndarray, px: float, py: float, r: float, eye_type: str) -> None:
    """Vectorized pupil mask."""
    h, w = base_arr.shape[:2]
    y_grid, x_grid = np.ogrid[:h, :w]
    if eye_type == "dragon":
        mask = (np.abs(x_grid - px) / max(2.0, r * 0.35)) + (np.abs(y_grid - py) / r) <= 1.0
    else:
        mask = (x_grid - px) ** 2 + (y_grid - py) ** 2 <= r**2
    base_arr[mask] = 0


def render_spinner(angle_rad: float, mirror: bool = True, color_phase: float = 0.0) -> object:
    """
    Vectorized NumPy spinner: smooth rotating ring with a gap.
    color_phase in [0, 1]: 0 = beige, 1 = green (one-way transition over startup).
    """
    size = config.EYE_SIZE
    # 1. Create coordinate grid
    y_idx, x_idx = np.indices((size, size), dtype=np.float32)
    cx, cy = size / 2.0, size / 2.0

    # 2. Ring matches default eye iris/pupil size (same as build_eye_base sclera/iris)
    r_out = config.IRIS_R * config.EYE_LAYER_VIEWPORT_SCALE  # iris outer edge
    r_in = float(config.eye_type_pupil_radii("default")[0])  # relaxed pupil = inner edge
    dist_sq = (x_idx - cx) ** 2 + (y_idx - cy) ** 2
    ring_mask = (dist_sq <= r_out**2) & (dist_sq >= r_in**2)

    # Softer AA edges: wider falloff so the ring doesn't look stepped
    dist = np.sqrt(dist_sq)
    half_width = (r_out - r_in) / 2.0
    mid_r = (r_out + r_in) / 2.0
    edge_dist = np.abs(dist - mid_r) - half_width
    falloff_px = 3.0  # spread over ~3 px for smoother blend
    edge_mask = np.clip(1.0 - edge_dist / falloff_px, 0, 1)

    # 3. Angular check for the gap (all angles in [0, 2π] for consistent comparison)
    pixel_angles = np.arctan2(y_idx - cy, x_idx - cx)  # [-π, π]
    pixel_angles = np.where(pixel_angles < 0, pixel_angles + 2 * math.pi, pixel_angles)  # [0, 2π]

    a0 = angle_rad % (2 * math.pi)
    gap_width = math.radians(60)
    a1 = (a0 + gap_width) % (2 * math.pi)

    if a0 < a1:
        gap_mask = (pixel_angles >= a0) & (pixel_angles <= a1)
    else:
        gap_mask = (pixel_angles >= a0) | (pixel_angles <= a1)

    # Angular distance from a0 (trailing edge of C) so we can fade in the gap
    two_pi = 2 * math.pi
    d = np.where(pixel_angles >= a0, pixel_angles - a0, (two_pi - a0) + pixel_angles)
    t = np.clip(d / gap_width, 0.0, 1.0)  # t=0 at C edge (beige), t=1 into gap (black)

    # 4. Ring color: step from beige to green (from config)
    beige = np.array(config.WARMUP_BEIGE, dtype=np.float64)
    green = np.array(config.WARMUP_GREEN, dtype=np.float64)
    num_steps = config.EYE_WARMUP_STEPS
    p = max(0, min(1, color_phase))
    step = min(int(round(p * (num_steps - 1))), num_steps - 1)
    blend_t = step / (num_steps - 1) if num_steps > 1 else 0
    ring_color = (1 - blend_t) * beige + blend_t * green

    out_arr = np.zeros((size, size, 3), dtype=np.uint8)
    final_mask = ring_mask & ~gap_mask
    out_arr[final_mask] = np.clip(ring_color, 0, 255).astype(np.uint8)
    gap_ring_mask = ring_mask & gap_mask
    blend = (1.0 - t[gap_ring_mask])[:, np.newaxis] * ring_color
    out_arr[gap_ring_mask] = np.clip(blend, 0, 255).astype(np.uint8)

    # Apply soft edge mask for organic, anti-aliased inner/outer ring edges
    out_arr = np.clip(out_arr.astype(np.float64) * edge_mask[:, :, np.newaxis], 0, 255).astype(np.uint8)

    if mirror:
        out_arr = np.flip(out_arr, axis=1)

    return Image.fromarray(out_arr)


def render_blink_overlay(mirror: bool = False) -> object | None:
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
        flip = getattr(Image, "FLIP_LEFT_RIGHT", 0)
        overlay = overlay.transpose(flip)  # pyright: ignore[reportArgumentType]

    _blink_overlay_cache[key] = overlay
    return overlay


def render_animated_frame(
    cached_eye_base_240: object | None,
    pupil_x: float,
    pupil_y: float,
    blink_state: str = "open",
    pupil_radius: int | float | None = None,
) -> object:
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
        resampling = getattr(Image, "Resampling", Image)
        resample = getattr(resampling, "LANCZOS", 1)
        result = result.resize((config.EYE_SIZE, config.EYE_SIZE), resample)

    return result


def preload_all_types(skip_type: str | None = None) -> None:
    """
    Pre-loads textures and initial gaze mappings for all eye types.
    Run in background at startup so switching is instantaneous.
    skip_type: if set, skip this type (main thread will load it on first frame).
    """
    eye_types = ["default", "human", "dragon", "demon"]
    center = config.EYE_SIZE // 2

    for etype in eye_types:
        if skip_type and etype == skip_type:
            continue
        try:
            _get_textures_numpy(etype)
            _get_eye_base_cached_numpy(center, center, force_type=etype)
        except Exception:
            pass
