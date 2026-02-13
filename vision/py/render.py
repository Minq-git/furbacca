"""
Render eye layer: spherical sampling, sclera+iris base, gaze cache, blink overlay, animated frame.
"""
import math

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    Image = None

import config
import assets
import shapes

_eye_base_sclera_iris_by_type = {}
_gaze_cache = {}  # (eye_type, qx_idx, qy_idx) -> PIL image
_blink_overlay_cache = {}  # shape_name -> PIL image (blink line follows eye shape)


def _sample_texture_spherical(tex, cx, cy, r_max, x, y, invert_v=False):
    """
    Sample texture with spherical mapping. v = r/r_max (0=center, 1=edge).
    Default: bottom of texture = center, top = outer edge. invert_v=True (human): bottom = outer edge, top = center.
    Returns (sx, sy) in texture coords or None if (x,y) outside circle.
    """
    dx, dy = x - cx, y - cy
    r = math.sqrt(dx * dx + dy * dy)
    if r > r_max:
        return None
    angle = math.atan2(dy, dx)
    u = (angle + math.pi) / (2.0 * math.pi)
    v = r / r_max
    w, h = tex.size
    sx = int(u * (w - 1) + 0.5) % w
    if invert_v:
        sy = int(v * (h - 1) + 0.5)
    else:
        sy = int((1.0 - v) * (h - 1) + 0.5)
    sy = max(0, min(h - 1, sy))
    return (sx, sy)


def build_eye_base_sclera_iris():
    """
    Build open-eye base: sclera (background) + iris (circular region). Cached per eye type.
    """
    global _eye_base_sclera_iris_by_type
    eye_type = config.get_eye_type()
    if eye_type in _eye_base_sclera_iris_by_type:
        return _eye_base_sclera_iris_by_type[eye_type]
    if not HAS_PIL:
        return None
    sclera = assets.load_sclera_image(eye_type)
    iris = assets.load_iris_image(eye_type)
    if sclera is None:
        _eye_base_sclera_iris_by_type[eye_type] = assets.load_iris_image(eye_type)
        return _eye_base_sclera_iris_by_type[eye_type]
    invert_v, iris_scale, sclera_scale = config.eye_type_scales(eye_type)
    cx, cy = config.EYE_SIZE // 2, config.EYE_SIZE // 2
    R_eye = int((config.EYE_SIZE // 2) * config.EYE_LAYER_VIEWPORT_SCALE * sclera_scale)
    iris_r_scaled = int(config.IRIS_R * iris_scale * config.EYE_LAYER_VIEWPORT_SCALE)
    base = Image.new("RGB", (config.EYE_SIZE, config.EYE_SIZE), (0, 0, 0))
    sclera_pix = sclera.load()
    base_pix = base.load()
    for y in range(config.EYE_SIZE):
        for x in range(config.EYE_SIZE):
            pt = _sample_texture_spherical(sclera, cx, cy, R_eye, x, y, invert_v=invert_v)
            if pt is not None:
                base_pix[x, y] = sclera_pix[pt[0], pt[1]]
    if iris is not None:
        iris_pix = iris.load()
        for y in range(config.EYE_SIZE):
            for x in range(config.EYE_SIZE):
                pt = _sample_texture_spherical(iris, cx, cy, iris_r_scaled, x, y, invert_v=invert_v)
                if pt is not None:
                    base_pix[x, y] = iris_pix[pt[0], pt[1]]
    _eye_base_sclera_iris_by_type[eye_type] = base
    return base


def build_eye_base_sclera_iris_at_center(pole_x, pole_y, eye_type=None, size=None):
    """
    Build open-eye base with spherical mapping centered at (pole_x, pole_y).
    pole_x, pole_y in EYE_SIZE space. size: output size (default EYE_SIZE).
    """
    if not HAS_PIL:
        return None
    if eye_type is None:
        eye_type = config.get_eye_type()
    if size is None:
        size = config.EYE_SIZE
    invert_v, iris_scale, sclera_scale = config.eye_type_scales(eye_type)
    sclera = assets.load_sclera_image(eye_type)
    iris = assets.load_iris_image(eye_type)
    if sclera is None:
        return assets.load_iris_image(eye_type)
    scale = size / config.EYE_SIZE
    pole_x_s = pole_x * scale
    pole_y_s = pole_y * scale
    R_eye = int((size // 2) * config.EYE_LAYER_VIEWPORT_SCALE * sclera_scale)
    iris_r_scaled = int(config.IRIS_R * iris_scale * config.EYE_LAYER_VIEWPORT_SCALE * scale)
    base = Image.new("RGB", (size, size), (0, 0, 0))
    sclera_pix = sclera.load()
    base_pix = base.load()
    for y in range(size):
        for x in range(size):
            pt = _sample_texture_spherical(sclera, pole_x_s, pole_y_s, R_eye, x, y, invert_v=invert_v)
            if pt is not None:
                base_pix[x, y] = sclera_pix[pt[0], pt[1]]
    if iris is not None:
        iris_pix = iris.load()
        for y in range(size):
            for x in range(size):
                pt = _sample_texture_spherical(iris, pole_x_s, pole_y_s, iris_r_scaled, x, y, invert_v=invert_v)
                if pt is not None:
                    base_pix[x, y] = iris_pix[pt[0], pt[1]]
    return base


def _get_eye_base_cached(px, py):
    """Return a copy of the eye base for quantized (px, py); build and cache on miss (Option A)."""
    global _gaze_cache
    cx, cy = config.EYE_SIZE // 2, config.EYE_SIZE // 2
    pupil_x = (px - cx) / 35.0
    pupil_y = (py - cy) / 35.0
    step = config.EYE_GAZE_CACHE_STEP
    qx_idx = round(pupil_x / step)
    qy_idx = round(pupil_y / step)
    eye_type = config.get_eye_type()
    key = (eye_type, qx_idx, qy_idx)
    if key not in _gaze_cache:
        qx = qx_idx * step
        qy = qy_idx * step
        qpx = int(cx + qx * 35)
        qpy = int(cy + qy * 35)
        _gaze_cache[key] = build_eye_base_sclera_iris_at_center(qpx, qpy, eye_type=eye_type, size=config.EYE_BUILD_SIZE)
        if _gaze_cache[key] is None:
            _gaze_cache[key] = Image.new("RGB", (config.EYE_BUILD_SIZE, config.EYE_BUILD_SIZE), (32, 32, 48))
    base = _gaze_cache[key]
    if base is None:
        return None
    return base.copy()


def render_blink_overlay(shape_name=None, mirror=False):
    """Blink layer only: black + eyelid line. Line follows eye shape (e.g. angular for sharp). mirror=True for right eye. Cached per (shape, mirror)."""
    if not HAS_PIL:
        return None
    from PIL import ImageDraw
    shape_name = (shape_name or config.get_eye_shape() or "round").strip().lower()
    size = config.EYE_SIZE
    key = (shape_name, mirror)
    if key in _blink_overlay_cache:
        return _blink_overlay_cache[key]
    overlay = Image.new("RGB", (size, size), (0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    (x0, y0), (x1, y1) = shapes.get_blink_line(shape_name, size)
    draw.line([(x0, y0), (x1, y1)], fill=(28, 28, 28), width=3)
    if mirror:
        overlay = overlay.transpose(Image.FLIP_LEFT_RIGHT)
    _blink_overlay_cache[key] = overlay
    return overlay


def render_animated_frame(cached_eye_base_240, pupil_x, pupil_y, blink_state="open", pupil_radius=None):
    """
    Renders the EYE LAYER only (sclera + iris + pupil). Option A: gaze cache. Option C: build at EYE_BUILD_SIZE then scale up.
    """
    cx, cy = config.EYE_SIZE // 2, config.EYE_SIZE // 2
    if pupil_radius is None:
        pupil_radius = float(config.eye_type_pupil_radii(config.get_eye_type())[0])
    r = max(8.0, min(60.0, float(pupil_radius)))
    px = int(cx + pupil_x * 35)
    py = int(cy + pupil_y * 35)

    base = _get_eye_base_cached(px, py)
    if base is None:
        base = Image.new("RGB", (config.EYE_BUILD_SIZE, config.EYE_BUILD_SIZE), (32, 32, 48)) if cached_eye_base_240 is None else cached_eye_base_240.resize((config.EYE_BUILD_SIZE, config.EYE_BUILD_SIZE), getattr(Image, "Resampling", Image).LANCZOS)
    scale_build = config.EYE_BUILD_SIZE / config.EYE_SIZE
    px_b, py_b = px * scale_build, py * scale_build
    r_b = r * scale_build
    base_pix = base.load()
    eye_type = config.get_eye_type()
    x0 = max(0, int(px_b - r_b - 1))
    y0 = max(0, int(py_b - r_b - 1))
    x1 = min(config.EYE_BUILD_SIZE, int(px_b + r_b + 2))
    y1 = min(config.EYE_BUILD_SIZE, int(py_b + r_b + 2))
    if eye_type == "dragon":
        half_w = max(2.0, r_b * 0.35)
        half_h = r_b
        for y in range(y0, y1):
            for x in range(x0, x1):
                if (abs(x - px_b) / half_w) + (abs(y - py_b) / half_h) <= 1.0:
                    base_pix[x, y] = (0, 0, 0)
    else:
        r_sq = r_b * r_b
        for y in range(y0, y1):
            for x in range(x0, x1):
                if (x - px_b) * (x - px_b) + (y - py_b) * (y - py_b) <= r_sq:
                    base_pix[x, y] = (0, 0, 0)
    if config.EYE_BUILD_SIZE != config.EYE_SIZE:
        resample = getattr(Image, "Resampling", Image).LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
        base = base.resize((config.EYE_SIZE, config.EYE_SIZE), resample)
    return base
