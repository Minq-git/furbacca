"""
Furbacca vision: dual GC9A01 eyes using russhughes/gc9a01py (CPython compat layer).
"""
import socket
import json
import time
import os
import sys

# Optional: PIL for image-based eyes
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

EYE_SIZE = 240
# Iris circle radius in pixels (from eye.svg: iris path radius 17.7 in 68px viewBox, eye radius 34 → 120*17.7/34 ≈ 62)
IRIS_R = int((EYE_SIZE // 2) * 17.7 / 34)
# Eye layer drawn 10% larger than viewport so when the eye moves we don't see black edges around the sclera
EYE_LAYER_VIEWPORT_SCALE = 1.25
left_eye = None
right_eye = None

# Optional: swap which SPI device is "left" vs "right"
SWAP_LEFT_RIGHT_SPI = os.environ.get("SWAP_LEFT_RIGHT_SPI", "").strip().lower() in ("1", "true", "yes")
# Optional: only show solid red/blue (no eye image)
EYES_SOLID_COLORS = os.environ.get("EYES_SOLID_COLORS", "").strip().lower() in ("1", "true", "yes")
# Optional: show gradient/rainbow instead of image (useful to test SPI without PIL/image file)
EYES_GRADIENT = os.environ.get("EYES_GRADIENT", "").strip().lower() in ("1", "true", "yes")
EYES_RAINBOW = os.environ.get("EYES_RAINBOW", "").strip().lower() in ("1", "true", "yes")
# Optional: headless animated eyes (PIL-rendered, no monitor) — iris + pupil + blink
EYES_ANIMATED = os.environ.get("EYES_ANIMATED", "").strip().lower() in ("1", "true", "yes")
# Optional: eye configuration — default, human (inverted: bottom=outside), dragon (dragon-*), demon (dragon-* + inverted)
_eye_type_raw = os.environ.get("EYE_TYPE", "").strip().lower()
def get_eye_type():
    if _eye_type_raw in ("human", "dragon", "demon"):
        return _eye_type_raw
    return "default"
EYE_TYPE = get_eye_type()

# --- Display: gc9a01py via compat layer ---
_vision_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _vision_dir)
try:
    from display import init_displays
    left_eye, right_eye = init_displays(swap_left_right=SWAP_LEFT_RIGHT_SPI)
except Exception as e:
    print(f"⚠ Display init failed: {e}")
    import traceback
    traceback.print_exc()
    left_eye, right_eye = None, None

# --- UDP bridge ---
UDP_IP = "127.0.0.1"
UDP_PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((UDP_IP, UDP_PORT))
sock.setblocking(False)


def _graphics_dir():
    return os.path.join(_vision_dir, "graphics")


_eye_image_pil = None
_sclera_by_type = {}
_iris_by_type = {}


def load_eye_image():
    """Load 240x240 image from vision/graphics/ (PIL). Fallback for static/non-animated mode."""
    global _eye_image_pil
    if _eye_image_pil is not None:
        return _eye_image_pil
    if not HAS_PIL:
        return None
    gdir = _graphics_dir()
    for name in ("eye.png", "eye.jpg", "iris.png", "iris.jpg", "sclera.png", "dragon-iris.jpg"):
        path = os.path.join(gdir, name)
        if os.path.isfile(path):
            try:
                img = Image.open(path).convert("RGB")
                resample = getattr(Image, "Resampling", Image).LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
                img = img.resize((EYE_SIZE, EYE_SIZE), resample)
                _eye_image_pil = img
                return _eye_image_pil
            except Exception as e:
                print(f"⚠ Could not load {path}: {e}")
    return None


def load_sclera_image(eye_type=None):
    """Load sclera texture (background / white of eye). eye_type: default, human (same assets), dragon (dragon-sclera). Cached per type."""
    global _sclera_by_type
    if eye_type is None:
        eye_type = get_eye_type()
    if eye_type in _sclera_by_type:
        return _sclera_by_type[eye_type]
    if not HAS_PIL:
        return None
    gdir = _graphics_dir()
    names = ("dragon-sclera.png",) if eye_type in ("dragon", "demon") else ("sclera.png",)
    for name in names:
        path = os.path.join(gdir, name)
        if os.path.isfile(path):
            try:
                img = Image.open(path).convert("RGB")
                resample = getattr(Image, "Resampling", Image).LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
                img = img.resize((EYE_SIZE, EYE_SIZE), resample)
                _sclera_by_type[eye_type] = img
                return img
            except Exception as e:
                print(f"⚠ Could not load sclera {path}: {e}")
    return None


def load_iris_image(eye_type=None):
    """Load iris texture (colored ring). eye_type: default, human (same assets), dragon (dragon-iris). Cached per type."""
    global _iris_by_type
    if eye_type is None:
        eye_type = get_eye_type()
    if eye_type in _iris_by_type:
        return _iris_by_type[eye_type]
    if not HAS_PIL:
        return None
    gdir = _graphics_dir()
    names = ("dragon-iris.jpg",) if eye_type in ("dragon", "demon") else ("iris.png", "iris.jpg")
    for name in names:
        path = os.path.join(gdir, name)
        if os.path.isfile(path):
            try:
                img = Image.open(path).convert("RGB")
                resample = getattr(Image, "Resampling", Image).LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
                img = img.resize((EYE_SIZE, EYE_SIZE), resample)
                _iris_by_type[eye_type] = img
                return img
            except Exception as e:
                print(f"⚠ Could not load iris {path}: {e}")
    return None


FB1_PATH = "/dev/fb1"
_fb1_warned = False

def _write_fb1(row_buf_or_full_buffer):
    """Write buffer (row or full frame) to /dev/fb1. LE RGB565. Needs sudo for /dev/fb1."""
    global _fb1_warned
    try:
        with open(FB1_PATH, "wb") as fb:
            if isinstance(row_buf_or_full_buffer, (list, tuple)):
                for row in row_buf_or_full_buffer:
                    fb.write(row)
            else:
                fb.write(row_buf_or_full_buffer)
    except PermissionError:
        if not _fb1_warned:
            print("⚠ Left eye (fb1): run with sudo for /dev/fb1 write access.")
            _fb1_warned = True
    except Exception as e:
        print(f"⚠ fb1 write error: {e}")

def show_eye_image_fb1():
    """Draw eye image to /dev/fb1 (left eye when overlay is used). LE RGB565."""
    img = load_eye_image()
    if img is None:
        return
    try:
        import struct
        img = img.rotate(180)
        rows = []
        for y in range(EYE_SIZE):
            row_buf = bytearray(EYE_SIZE * 2)
            for x in range(EYE_SIZE):
                r, g, b = img.getpixel((x, y))
                c565 = (r & 0xF8) << 8 | (g & 0xFC) << 3 | (b >> 3)
                row_buf[x * 2 : x * 2 + 2] = struct.pack("<H", c565)
            rows.append(row_buf)
        _write_fb1(rows)
    except Exception as e:
        print(f"⚠ Show image fb1 error: {e}")

def fill_fb1(color_565):
    """Fill /dev/fb1 with solid color (16-bit RGB565, little-endian)."""
    import struct
    row = struct.pack("<H", color_565) * EYE_SIZE
    _write_fb1([row] * EYE_SIZE)


def _rgb565_le(r, g, b):
    """Pack R,G,B (0-255) to little-endian RGB565 (gradient/rainbow/fb1)."""
    import struct
    c565 = (r & 0xF8) << 8 | (g & 0xFC) << 3 | (b >> 3)
    return struct.pack("<H", c565)


def _rgb565_be(r, g, b):
    """Pack R,G,B (0-255) to big-endian RGB565. Required for eye image on gc9a01py (iris displays correctly with >H)."""
    import struct
    c565 = (r & 0xF8) << 8 | (g & 0xFC) << 3 | (b >> 3)
    return struct.pack(">H", c565)


def show_gradient(display):
    """Draw XY gradient (red/green sweep) to display. No image file; same blit path as show_eye_image."""
    if display is None:
        return
    try:
        row_buf = bytearray(EYE_SIZE * 2)
        for y in range(EYE_SIZE):
            for x in range(EYE_SIZE):
                r = x * 255 // (EYE_SIZE - 1) if EYE_SIZE > 1 else 0
                g = y * 255 // (EYE_SIZE - 1) if EYE_SIZE > 1 else 0
                b = 128
                row_buf[x * 2 : x * 2 + 2] = _rgb565_le(r, g, b)
            display.blit_buffer(row_buf, 0, y, EYE_SIZE, 1)
    except Exception as e:
        print(f"⚠ Gradient error: {e}")


def _hsv_to_rgb(h, s, v):
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


def show_rainbow(display):
    """Draw circular rainbow (hue by angle from center) to display. Same blit path as show_eye_image."""
    if display is None:
        return
    try:
        import math
        cx = (EYE_SIZE - 1) / 2.0
        cy = (EYE_SIZE - 1) / 2.0
        row_buf = bytearray(EYE_SIZE * 2)
        for y in range(EYE_SIZE):
            for x in range(EYE_SIZE):
                dx, dy = x - cx, y - cy
                angle = math.atan2(dy, dx)
                hue = (angle / (2 * math.pi) + 0.5) % 1.0
                r, g, b = _hsv_to_rgb(hue, 1.0, 1.0)
                row_buf[x * 2 : x * 2 + 2] = _rgb565_le(r, g, b)
            display.blit_buffer(row_buf, 0, y, EYE_SIZE, 1)
    except Exception as e:
        print(f"⚠ Rainbow error: {e}")


def _pil_to_rgb565_be_buffer(img):
    """Convert 240x240 PIL RGB to bytearray big-endian RGB565 (row-major). Same as show_eye_image (>H) so iris displays correctly."""
    if img.mode != "RGB":
        img = img.convert("RGB")
    if img.size != (EYE_SIZE, EYE_SIZE):
        img = img.resize((EYE_SIZE, EYE_SIZE), getattr(Image, "Resampling", Image).LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS)
    img = img.rotate(180)
    buf = bytearray(EYE_SIZE * EYE_SIZE * 2)
    for y in range(EYE_SIZE):
        for x in range(EYE_SIZE):
            r, g, b = img.getpixel((x, y))
            offset = (y * EYE_SIZE + x) * 2
            buf[offset : offset + 2] = _rgb565_be(r, g, b)
    return buf


def _blit_buffer_row_by_row(display, buf):
    """Blit RGB565 buffer to display row-by-row (same as show_eye_image / gradient path; avoids full-frame noise)."""
    if display is None or buf is None:
        return
    for y in range(EYE_SIZE):
        display.blit_buffer(buf[y * EYE_SIZE * 2 : (y + 1) * EYE_SIZE * 2], 0, y, EYE_SIZE, 1)


def _blit_buffer_full_frame_both(buf):
    """Blit full 240x240 buffer to both displays in one call per display. Reduces visible scanline by updating the whole frame at once (vsync-like)."""
    if buf is None or len(buf) < EYE_SIZE * EYE_SIZE * 2:
        return
    if left_eye is not None:
        left_eye.blit_buffer(buf, 0, 0, EYE_SIZE, EYE_SIZE)
    if right_eye is not None:
        right_eye.blit_buffer(buf, 0, 0, EYE_SIZE, EYE_SIZE)


def _blit_buffer_row_by_row_both(buf, reverse_rows=False, outside_in=False, inside_out=False, partial_rows=None):
    """Blit same buffer row-by-row. partial_rows=(y0,y1)=only those rows (faster when only pupil/eyelid changes)."""
    if buf is None:
        return
    y_lo, y_hi = (partial_rows if partial_rows else (0, EYE_SIZE - 1))
    y_lo = max(0, min(EYE_SIZE - 1, y_lo))
    y_hi = max(y_lo, min(EYE_SIZE - 1, y_hi))
    if outside_in:
        ys = []
        for i in range(EYE_SIZE):
            y = (EYE_SIZE - 1 - (i // 2)) if i % 2 == 0 else (i // 2)
            ys.append(y)
    elif inside_out:
        center = EYE_SIZE // 2
        ys = [center]
        for offset in range(1, center + 1):
            if center - offset >= 0:
                ys.append(center - offset)
            if center + offset < EYE_SIZE:
                ys.append(center + offset)
    elif reverse_rows:
        ys = list(range(EYE_SIZE - 1, -1, -1))
    else:
        ys = list(range(EYE_SIZE))
    if partial_rows is not None:
        ys = [y for y in ys if y_lo <= y <= y_hi]
    for y in ys:
        row = buf[y * EYE_SIZE * 2 : (y + 1) * EYE_SIZE * 2]
        if left_eye is not None:
            left_eye.blit_buffer(row, 0, y, EYE_SIZE, 1)
        if right_eye is not None:
            right_eye.blit_buffer(row, 0, y, EYE_SIZE, 1)


def _blit_pil_to_display(display, img):
    """Blit a 240x240 PIL RGB image to one display. Big-endian RGB565 row-by-row (same path as show_eye_image)."""
    if display is None or img is None:
        return
    buf = _pil_to_rgb565_be_buffer(img)
    _blit_buffer_row_by_row(display, buf)


def _blit_pil_to_both(img, reverse_rows=False, outside_in=False, inside_out=False, partial_rows=None):
    """Blit same PIL image to both displays. Full-frame top-down uses single blit per display (vsync-like, no scanline)."""
    if img is None:
        return
    buf = _pil_to_rgb565_be_buffer(img)
    if not reverse_rows and not outside_in and not inside_out and partial_rows is None:
        _blit_buffer_full_frame_both(buf)
    else:
        _blit_buffer_row_by_row_both(buf, reverse_rows=reverse_rows, outside_in=outside_in, inside_out=inside_out, partial_rows=partial_rows)


_eye_base_sclera_iris_by_type = {}


def _sample_texture_spherical(tex, cx, cy, r_max, x, y, invert_v=False):
    """
    Sample texture with spherical mapping. v = r/r_max (0=center, 1=edge).
    Default: bottom of texture = center, top = outer edge. invert_v=True (human): bottom = outer edge, top = center.
    Returns (sx, sy) in texture coords or None if (x,y) outside circle.
    """
    import math
    dx, dy = x - cx, y - cy
    r = math.sqrt(dx * dx + dy * dy)
    if r > r_max:
        return None
    angle = math.atan2(dy, dx)
    u = (angle + math.pi) / (2.0 * math.pi)  # 0..1 around circle
    v = r / r_max  # 0 at center, 1 at edge
    w, h = tex.size
    sx = int(u * (w - 1) + 0.5) % w
    if invert_v:
        sy = int(v * (h - 1) + 0.5)  # v=0 → top (0), v=1 → bottom (h-1): bottom of image = outside
    else:
        sy = int((1.0 - v) * (h - 1) + 0.5)  # v=0 → bottom (h-1), v=1 → top (0)
    sy = max(0, min(h - 1, sy))
    return (sx, sy)


def build_eye_base_sclera_iris():
    """
    Build open-eye base: sclera (background) + iris (circular region), per eye.svg / PI_Eyes.
    Uses EYE_TYPE: default (normal), human (inverted), dragon (dragon-*), demon (dragon-* + inverted). Cached per eye type.
    """
    global _eye_base_sclera_iris_by_type
    eye_type = get_eye_type()
    if eye_type in _eye_base_sclera_iris_by_type:
        return _eye_base_sclera_iris_by_type[eye_type]
    if not HAS_PIL:
        return None
    sclera = load_sclera_image(eye_type)
    iris = load_iris_image(eye_type)
    if sclera is None:
        _eye_base_sclera_iris_by_type[eye_type] = load_iris_image(eye_type)  # fallback: iris only
        return _eye_base_sclera_iris_by_type[eye_type]
    invert_v = eye_type in ("human", "demon")
    cx, cy = EYE_SIZE // 2, EYE_SIZE // 2
    R_eye = int((EYE_SIZE // 2) * EYE_LAYER_VIEWPORT_SCALE)
    iris_r_scaled = int(IRIS_R * EYE_LAYER_VIEWPORT_SCALE)
    base = Image.new("RGB", (EYE_SIZE, EYE_SIZE), (0, 0, 0))
    sclera_pix = sclera.load()
    base_pix = base.load()
    for y in range(EYE_SIZE):
        for x in range(EYE_SIZE):
            pt = _sample_texture_spherical(sclera, cx, cy, R_eye, x, y, invert_v=invert_v)
            if pt is not None:
                base_pix[x, y] = sclera_pix[pt[0], pt[1]]
    if iris is not None:
        iris_pix = iris.load()
        for y in range(EYE_SIZE):
            for x in range(EYE_SIZE):
                pt = _sample_texture_spherical(iris, cx, cy, iris_r_scaled, x, y, invert_v=invert_v)
                if pt is not None:
                    base_pix[x, y] = iris_pix[pt[0], pt[1]]
    _eye_base_sclera_iris_by_type[eye_type] = base
    return base


def build_eye_base_sclera_iris_at_center(pole_x, pole_y):
    """
    Build open-eye base with spherical mapping centered at (pole_x, pole_y).
    Sclera and iris follow the pupil (eyeball follows gaze). Uses EYE_TYPE (default/human/dragon/demon). Returns 240x240 RGB or None.
    """
    if not HAS_PIL:
        return None
    eye_type = get_eye_type()
    invert_v = eye_type in ("human", "demon")
    sclera = load_sclera_image(eye_type)
    iris = load_iris_image(eye_type)
    if sclera is None:
        return load_iris_image(eye_type)  # fallback: iris only, flat (no spherical at center)
    R_eye = int((EYE_SIZE // 2) * EYE_LAYER_VIEWPORT_SCALE)
    iris_r_scaled = int(IRIS_R * EYE_LAYER_VIEWPORT_SCALE)
    base = Image.new("RGB", (EYE_SIZE, EYE_SIZE), (0, 0, 0))
    sclera_pix = sclera.load()
    base_pix = base.load()
    for y in range(EYE_SIZE):
        for x in range(EYE_SIZE):
            pt = _sample_texture_spherical(sclera, pole_x, pole_y, R_eye, x, y, invert_v=invert_v)
            if pt is not None:
                base_pix[x, y] = sclera_pix[pt[0], pt[1]]
    if iris is not None:
        iris_pix = iris.load()
        for y in range(EYE_SIZE):
            for x in range(EYE_SIZE):
                pt = _sample_texture_spherical(iris, pole_x, pole_y, iris_r_scaled, x, y, invert_v=invert_v)
                if pt is not None:
                    base_pix[x, y] = iris_pix[pt[0], pt[1]]
    return base


_blink_overlay_240 = None


def render_blink_overlay():
    """Blink layer only: black + eyelid line. Cached. Blit this separately with outside_in/inside_out."""
    global _blink_overlay_240
    if _blink_overlay_240 is not None:
        return _blink_overlay_240
    if not HAS_PIL:
        return None
    from PIL import ImageDraw
    overlay = Image.new("RGB", (EYE_SIZE, EYE_SIZE), (0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    cy = EYE_SIZE // 2
    line_y = cy
    for dy in (-1, 0, 1):
        draw.line([(0, line_y + dy), (EYE_SIZE, line_y + dy)], fill=(28, 28, 28), width=1)
    _blink_overlay_240 = overlay
    return _blink_overlay_240


def render_animated_frame(cached_eye_base_240, pupil_x, pupil_y, blink_state="open", pupil_radius=None):
    """
    Renders the EYE LAYER only (sclera + iris + pupil). Always the open eye.
    Blink is drawn on a separate layer (render_blink_overlay) and blit with outside_in/inside_out.
    pupil_radius: optional float; if None uses 22. Uses float radius for smooth dilation (no integer snap).
    """
    cx, cy = EYE_SIZE // 2, EYE_SIZE // 2
    if pupil_radius is None:
        pupil_radius = 22.0
    r = max(8.0, min(40.0, float(pupil_radius)))
    px = int(cx + pupil_x * 35)
    py = int(cy + pupil_y * 35)

    # Always render open eye (eye layer is always top-down; blink is separate overlay)
    base = build_eye_base_sclera_iris_at_center(px, py)
    if base is None:
        base = Image.new("RGB", (EYE_SIZE, EYE_SIZE), (32, 32, 48)) if cached_eye_base_240 is None else cached_eye_base_240.copy()
    # Draw pupil with float radius (distance check) so dilation animates smoothly without integer stepping
    base_pix = base.load()
    r_sq = r * r
    x0 = max(0, int(px - r - 1))
    y0 = max(0, int(py - r - 1))
    x1 = min(EYE_SIZE, int(px + r + 2))
    y1 = min(EYE_SIZE, int(py + r + 2))
    for y in range(y0, y1):
        for x in range(x0, x1):
            if (x - px) * (x - px) + (y - py) * (y - py) <= r_sq:
                base_pix[x, y] = (0, 0, 0)
    return base


def show_constructed_eye():
    """Show the static constructed eyeball (sclera + iris + pupil at center) on both displays. No animation."""
    frame = render_animated_frame(build_eye_base_sclera_iris(), 0.0, 0.0, "open")
    if frame is not None:
        _blit_pil_to_both(frame, reverse_rows=False, outside_in=False, inside_out=False, partial_rows=None)
    else:
        # Fallback: single image if no sclera/iris
        show_eye_image(left_eye)
        if right_eye is not None:
            time.sleep(0.02)
            show_eye_image(right_eye)


def show_eye_image(display):
    """Send PIL image to gc9a01py display. Big-endian RGB565 row-by-row (PACK_FMT >H — known-good for iris on this hardware)."""
    img = load_eye_image()
    if img is None or display is None:
        return
    try:
        img = img.rotate(180)
        row_buf = bytearray(EYE_SIZE * 2)
        for y in range(EYE_SIZE):
            for x in range(EYE_SIZE):
                r, g, b = img.getpixel((x, y))
                c565 = (r & 0xF8) << 8 | (g & 0xFC) << 3 | (b >> 3)
                row_buf[x * 2 : x * 2 + 2] = _rgb565_be(r, g, b)
            display.blit_buffer(row_buf, 0, y, EYE_SIZE, 1)
    except Exception as e:
        print(f"⚠ Show image error: {e}")


def run_eyes():
    if left_eye is None and right_eye is None:
        print("❌ No displays initialized. Run scripts/fetch-gc9a01py.sh and ensure vision/machine_compat and vision/gc9a01py are present.")
        return

    print("👀 Furbacca Vision Online (gc9a01py).")
    use_gradient = EYES_GRADIENT
    use_rainbow = EYES_RAINBOW
    use_animated = EYES_ANIMATED and HAS_PIL and build_eye_base_sclera_iris() is not None
    use_image = not EYES_SOLID_COLORS and not use_gradient and not use_rainbow and not use_animated and (
        build_eye_base_sclera_iris() is not None or load_eye_image() is not None
    )

    def _show_idle():
        if use_gradient:
            show_gradient(left_eye)
            time.sleep(0.05)
            show_gradient(right_eye)
        elif use_rainbow:
            show_rainbow(left_eye)
            time.sleep(0.05)
            show_rainbow(right_eye)
        elif use_image:
            show_constructed_eye()
        else:
            if left_eye:
                left_eye.fill(0xF800)
            if right_eye:
                right_eye.fill(0x001F)

    if use_animated:
        print("  Animated eyes (headless, no monitor). UDP: blink, look x/y.")
        cached_eye_base_240 = build_eye_base_sclera_iris()
        import random
        import math
        # Ease curve 3*t^2 - 2*t^3 (smooth start/end, fast middle) ported from C; 256 entries 0..255
        EASE_TABLE = tuple(
            int(255.0 * (3.0 * (i / 255.0) ** 2 - 2.0 * (i / 255.0) ** 3))
            for i in range(256)
        )
        pupil_x, pupil_y = 0.0, 0.0
        target_x, target_y = 0.0, 0.0
        # Autonomous saccade-and-hold (like C: move to random point with ease curve, then hold)
        eye_in_motion = False
        eye_old_x, eye_old_y = 0.0, 0.0
        eye_new_x, eye_new_y = 0.0, 0.0
        eye_move_start = 0.0
        eye_move_duration = 0.0
        eye_hold_until = 0.0
        IDLE_LOOK_TIMEOUT = 0.2
        MOVE_DURATION_MIN, MOVE_DURATION_MAX = 0.072, 0.144
        HOLD_DURATION_MAX = 3.0
        # Blink: open 2–5 s, then closed (one duration), then open. Draw: closing = outside-in, opening = inside-out.
        blit_open_bottom_to_top = False  # first open frame after blink: refresh inside-out
        next_auto_blink = time.monotonic() + random.uniform(2.0, 5.0)  # open 2–5 s between blinks
        ANIM_FPS = 60
        frame_dt = 1.0 / ANIM_FPS
        PUPIL_EASE = 0.48
        BLINK_DEBOUNCE_S = 0.2
        last_blink_end = 0.0
        last_look_time = 0.0
        # Pupil size: relaxed 22, focused 12, wide 40 (dark room). Smooth eased transitions (same curve as blink/saccade).
        PUPIL_RADIUS_RELAXED = 22
        PUPIL_RADIUS_FOCUSED = 12
        PUPIL_RADIUS_WIDE = 40
        focus_until = 0.0
        wide_until = 0.0
        next_wide_at = 0.0
        FOCUS_HOLD_S = 0.35
        PUPIL_TRANSITION_S = 0.5   # longer so dilation feels gradual, not a snap
        pupil_radius_current = float(PUPIL_RADIUS_RELAXED)
        pupil_radius_target = PUPIL_RADIUS_RELAXED
        radius_transition_start = 0.0
        radius_transition_from = float(PUPIL_RADIUS_RELAXED)
        radius_transition_to = float(PUPIL_RADIUS_RELAXED)
        # Time-based blink: close then open (no hold when closed).
        blink_phase = None  # None | "closing"
        blink_start_time = 0.0
        closing_duration_s = 0.05   # ~50 ms closing
        CLOSING_S_MIN, CLOSING_S_MAX = 0.04, 0.07   # 40–70 ms

        def do_blink():
            nonlocal blink_phase, blink_start_time, closing_duration_s
            blink_phase = "closing"
            blink_start_time = time.monotonic()
            closing_duration_s = random.uniform(CLOSING_S_MIN, CLOSING_S_MAX)

        while True:
            now = time.monotonic()
            # UDP: drain all pending packets so head-trigger blink is not missed
            while True:
                try:
                    data, _ = sock.recvfrom(1024)
                    msg = json.loads(data.decode())
                    action = msg.get("action")
                    if action == "blink":
                        if now - last_blink_end >= BLINK_DEBOUNCE_S:
                            do_blink()
                            last_blink_end = now
                            print("🐾 Logic: Blinked both eyes.")
                    elif action == "look":
                        tx = msg.get("x")
                        ty = msg.get("y")
                        if tx is not None:
                            target_x = max(-1.0, min(1.0, float(tx)))
                        if ty is not None:
                            target_y = max(-1.0, min(1.0, float(ty)))
                        last_look_time = now
                        focus_until = now + FOCUS_HOLD_S
                except BlockingIOError:
                    break
                except json.JSONDecodeError:
                    pass

            # Auto blink: next time = 3 * last blink duration + 0–4 s (ported from C)
            if blink_phase is None and now >= next_auto_blink:
                do_blink()
                next_auto_blink = now + random.uniform(2.0, 5.0)

            # Advance blink phase: closing (40–70 ms) -> open (no closed hold)
            if blink_phase == "closing":
                if (now - blink_start_time) >= closing_duration_s:
                    blink_phase = None
                    blit_open_bottom_to_top = True
                    total_blink_s = now - blink_start_time
                    next_auto_blink = now + (total_blink_s * 3.0) + random.uniform(0.0, 4.0)

            # Map phase to visual state for render
            blink_state = "open" if blink_phase is None else "closed"

            # Pupil motion: UDP look drives target; when idle use saccade-and-hold with ease curve (ported from C)
            if (now - last_look_time) <= IDLE_LOOK_TIMEOUT:
                # Recent UDP look: ease toward target (same as before)
                pupil_x += (target_x - pupil_x) * PUPIL_EASE
                pupil_y += (target_y - pupil_y) * PUPIL_EASE
                pupil_x = max(-1.0, min(1.0, pupil_x))
                pupil_y = max(-1.0, min(1.0, pupil_y))
            else:
                # Idle: saccade-and-hold with 3*t^2 - 2*t^3 ease (smooth start/end, fast middle)
                if eye_in_motion:
                    elapsed = now - eye_move_start
                    if elapsed >= eye_move_duration:
                        eye_in_motion = False
                        pupil_x = eye_old_x = eye_new_x
                        pupil_y = eye_old_y = eye_new_y
                        eye_hold_until = now + random.uniform(0.0, HOLD_DURATION_MAX)
                        focus_until = now + FOCUS_HOLD_S
                    else:
                        t = elapsed / eye_move_duration
                        idx = min(255, int(t * 255))
                        e = (EASE_TABLE[idx] + 1) / 256.0
                        pupil_x = eye_old_x + (eye_new_x - eye_old_x) * e
                        pupil_y = eye_old_y + (eye_new_y - eye_old_y) * e
                else:
                    pupil_x = eye_old_x
                    pupil_y = eye_old_y
                    if now >= eye_hold_until:
                        # Pick new random point in unit circle (like C)
                        while True:
                            dx = random.uniform(-1.0, 1.0)
                            dy = random.uniform(-1.0, 1.0)
                            if dx * dx + dy * dy <= 1.0:
                                break
                        eye_old_x, eye_old_y = pupil_x, pupil_y
                        eye_new_x, eye_new_y = dx * 0.85, dy * 0.85
                        eye_move_start = now
                        eye_move_duration = random.uniform(MOVE_DURATION_MIN, MOVE_DURATION_MAX)
                        eye_in_motion = True
                pupil_x = max(-1.0, min(1.0, pupil_x))
                pupil_y = max(-1.0, min(1.0, pupil_y))

            # Pupil size: target = focused (12) when looking at something, wide (40) in "dark" moment, else relaxed (22). Eased transition.
            if now < focus_until:
                pupil_radius_target = PUPIL_RADIUS_FOCUSED
            elif now < wide_until:
                pupil_radius_target = PUPIL_RADIUS_WIDE
            else:
                pupil_radius_target = PUPIL_RADIUS_RELAXED
            if next_wide_at == 0.0:
                next_wide_at = now + random.uniform(25.0, 45.0)
            if now >= next_wide_at and pupil_radius_target == PUPIL_RADIUS_RELAXED:
                wide_until = now + random.uniform(1.0, 2.0)
                next_wide_at = now + random.uniform(25.0, 45.0)
            if pupil_radius_target != radius_transition_to:
                radius_transition_from = pupil_radius_current
                radius_transition_to = pupil_radius_target
                radius_transition_start = now
            elapsed = now - radius_transition_start
            if elapsed >= PUPIL_TRANSITION_S or radius_transition_from == radius_transition_to:
                pupil_radius_current = float(radius_transition_to)
            else:
                progress = elapsed / PUPIL_TRANSITION_S
                idx = min(255, int(progress * 255))
                e = EASE_TABLE[idx] / 255.0
                pupil_radius_current = radius_transition_from + (radius_transition_to - radius_transition_from) * e
            pupil_radius = pupil_radius_current

            # Eye layer: open eye (sclera + iris + pupil). Always full-frame blit (no inside_out/outside_in — that's only for blink overlay).
            eye_frame = render_animated_frame(cached_eye_base_240, pupil_x, pupil_y, "open", pupil_radius=pupil_radius)
            if blit_open_bottom_to_top:
                _blit_pil_to_both(eye_frame, reverse_rows=False, outside_in=False, inside_out=True, partial_rows=None)
                blit_open_bottom_to_top = False
            elif blink_state == "closed":
                # Composite eye + overlay in memory, then one blit (outside_in) so no flicker from two blits with different row orders.
                overlay = render_blink_overlay()
                if overlay is not None:
                    composite = eye_frame.copy()
                    composite.paste(overlay, (0, 0))
                    _blit_pil_to_both(composite, reverse_rows=False, outside_in=True, inside_out=False, partial_rows=None)
                else:
                    _blit_pil_to_both(eye_frame, reverse_rows=False, outside_in=False, inside_out=False, partial_rows=None)
            else:
                _blit_pil_to_both(eye_frame, reverse_rows=False, outside_in=False, inside_out=False, partial_rows=None)
            time.sleep(max(0.0, frame_dt - (time.monotonic() - now)))
        return

    if use_gradient:
        print("  Showing XY gradient on both displays (EYES_GRADIENT=1).")
        _show_idle()
    elif use_rainbow:
        print("  Showing rainbow on both displays (EYES_RAINBOW=1).")
        _show_idle()
    elif use_image:
        print("  Showing eye image on both displays...")
        _show_idle()
    else:
        if EYES_SOLID_COLORS:
            print("  Solid colors only (EYES_SOLID_COLORS=1).")
        if left_eye:
            left_eye.fill(0xF800)
        time.sleep(0.02)
        if right_eye:
            right_eye.fill(0x001F)

    def restore_idle():
        _show_idle()

    # Static blink: close then open (no hold when closed). Cache eye frame once so blink is instant.
    _static_eye_frame = render_animated_frame(build_eye_base_sclera_iris(), 0.0, 0.0, "open")
    BLINK_DEBOUNCE_S = 0.2
    last_blink_end = 0.0
    blink_phase = None  # None | "closing" | "opening"

    while True:
        now = time.monotonic()
        # Drain UDP so we see the head trigger immediately (no missed packets)
        while True:
            try:
                data, _ = sock.recvfrom(1024)
                msg = json.loads(data.decode())
                action = msg.get("action")
                if action == "blink" and (now - last_blink_end) >= BLINK_DEBOUNCE_S:
                    blink_phase = "closing"
                    last_blink_end = now
                    print("🐾 Logic: Blinked both eyes.")
            except BlockingIOError:
                break
            except json.JSONDecodeError:
                pass

        if blink_phase == "closing":
            if _static_eye_frame is not None:
                _blit_pil_to_both(_static_eye_frame, reverse_rows=False, outside_in=False, inside_out=False, partial_rows=None)
            overlay = render_blink_overlay()
            if overlay is not None:
                _blit_pil_to_both(overlay, reverse_rows=False, outside_in=True, inside_out=False, partial_rows=None)
            blink_phase = "opening"
        elif blink_phase == "opening":
            if _static_eye_frame is not None:
                _blit_pil_to_both(_static_eye_frame, reverse_rows=False, outside_in=False, inside_out=True, partial_rows=None)
            blink_phase = None

        time.sleep(0.02)


if __name__ == "__main__":
    run_eyes()
