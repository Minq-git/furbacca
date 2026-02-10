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
_sclera_pil = None
_iris_pil = None


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


def load_sclera_image():
    """Load sclera texture (background / white of eye). Used as bottom layer per eye.svg."""
    global _sclera_pil
    if _sclera_pil is not None:
        return _sclera_pil
    if not HAS_PIL:
        return None
    gdir = _graphics_dir()
    for name in ("sclera.png", "dragon-sclera.png"):
        path = os.path.join(gdir, name)
        if os.path.isfile(path):
            try:
                img = Image.open(path).convert("RGB")
                resample = getattr(Image, "Resampling", Image).LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
                _sclera_pil = img.resize((EYE_SIZE, EYE_SIZE), resample)
                return _sclera_pil
            except Exception as e:
                print(f"⚠ Could not load sclera {path}: {e}")
    return None


def load_iris_image():
    """Load iris texture (colored ring). Composites on top of sclera per eye.svg."""
    global _iris_pil
    if _iris_pil is not None:
        return _iris_pil
    if not HAS_PIL:
        return None
    gdir = _graphics_dir()
    for name in ("iris.png", "iris.jpg", "dragon-iris.jpg"):
        path = os.path.join(gdir, name)
        if os.path.isfile(path):
            try:
                img = Image.open(path).convert("RGB")
                resample = getattr(Image, "Resampling", Image).LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
                _iris_pil = img.resize((EYE_SIZE, EYE_SIZE), resample)
                return _iris_pil
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
    """Blit same PIL image to both displays. partial_rows=(y0,y1)=only those rows (update only pixels that change for fluid 60fps)."""
    if img is None:
        return
    buf = _pil_to_rgb565_be_buffer(img)
    _blit_buffer_row_by_row_both(buf, reverse_rows=reverse_rows, outside_in=outside_in, inside_out=inside_out, partial_rows=partial_rows)


_eye_base_sclera_iris = None


def _sample_texture_spherical(tex, cx, cy, r_max, x, y):
    """
    Sample texture with spherical mapping: bottom of texture = center (r=0), top = outer edge (r=r_max).
    Angle wraps horizontally. Returns (sx, sy) in texture coords or None if (x,y) outside circle.
    """
    import math
    dx, dy = x - cx, y - cy
    r = math.sqrt(dx * dx + dy * dy)
    if r > r_max:
        return None
    angle = math.atan2(dy, dx)
    u = (angle + math.pi) / (2.0 * math.pi)  # 0..1 around circle
    v = r / r_max  # 0 at center, 1 at edge → texture bottom at center, top at edge
    w, h = tex.size
    sx = int(u * (w - 1) + 0.5) % w
    sy = int((1.0 - v) * (h - 1) + 0.5)  # v=0 → bottom row (h-1), v=1 → top row (0)
    sy = max(0, min(h - 1, sy))
    return (sx, sy)


def build_eye_base_sclera_iris():
    """
    Build open-eye base: sclera (background) + iris (circular region), per eye.svg / PI_Eyes.
    Textures use spherical mapping: bottom of image = center of eye, top = outer rim (3D illusion).
    Returns 240x240 RGB or None if textures missing. Cached after first build.
    """
    global _eye_base_sclera_iris
    if _eye_base_sclera_iris is not None:
        return _eye_base_sclera_iris
    if not HAS_PIL:
        return None
    import math
    sclera = load_sclera_image()
    iris = load_iris_image()
    if sclera is None:
        _eye_base_sclera_iris = load_iris_image()  # fallback: iris only
        return _eye_base_sclera_iris
    cx, cy = EYE_SIZE // 2, EYE_SIZE // 2
    R_eye = EYE_SIZE // 2
    base = Image.new("RGB", (EYE_SIZE, EYE_SIZE), (0, 0, 0))
    sclera_pix = sclera.load()
    base_pix = base.load()
    for y in range(EYE_SIZE):
        for x in range(EYE_SIZE):
            pt = _sample_texture_spherical(sclera, cx, cy, R_eye, x, y)
            if pt is not None:
                base_pix[x, y] = sclera_pix[pt[0], pt[1]]
    if iris is not None:
        iris_pix = iris.load()
        for y in range(EYE_SIZE):
            for x in range(EYE_SIZE):
                pt = _sample_texture_spherical(iris, cx, cy, IRIS_R, x, y)
                if pt is not None:
                    base_pix[x, y] = iris_pix[pt[0], pt[1]]
    _eye_base_sclera_iris = base
    return _eye_base_sclera_iris


def build_eye_base_sclera_iris_at_center(pole_x, pole_y):
    """
    Build open-eye base with spherical mapping centered at (pole_x, pole_y).
    Sclera and iris follow the pupil (eyeball follows gaze). Returns 240x240 RGB or None.
    """
    if not HAS_PIL:
        return None
    sclera = load_sclera_image()
    iris = load_iris_image()
    if sclera is None:
        return load_iris_image()  # fallback: iris only, flat (no spherical at center)
    R_eye = EYE_SIZE // 2
    base = Image.new("RGB", (EYE_SIZE, EYE_SIZE), (0, 0, 0))
    sclera_pix = sclera.load()
    base_pix = base.load()
    for y in range(EYE_SIZE):
        for x in range(EYE_SIZE):
            pt = _sample_texture_spherical(sclera, pole_x, pole_y, R_eye, x, y)
            if pt is not None:
                base_pix[x, y] = sclera_pix[pt[0], pt[1]]
    if iris is not None:
        iris_pix = iris.load()
        for y in range(EYE_SIZE):
            for x in range(EYE_SIZE):
                pt = _sample_texture_spherical(iris, pole_x, pole_y, IRIS_R, x, y)
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


def render_animated_frame(cached_eye_base_240, pupil_x, pupil_y, blink_state="open"):
    """
    Renders the EYE LAYER only (sclera + iris + pupil). Always the open eye.
    Blink is drawn on a separate layer (render_blink_overlay) and blit with outside_in/inside_out.
    cached_eye_base_240: fallback when textures missing. Sclera and iris follow pupil (pole at pupil).
    """
    from PIL import ImageDraw
    cx, cy = EYE_SIZE // 2, EYE_SIZE // 2
    pupil_radius = 18
    px = int(cx + pupil_x * 35)
    py = int(cy + pupil_y * 35)

    # Always render open eye (eye layer is always top-down; blink is separate overlay)
    base = build_eye_base_sclera_iris_at_center(px, py)
    if base is None:
        base = Image.new("RGB", (EYE_SIZE, EYE_SIZE), (32, 32, 48)) if cached_eye_base_240 is None else cached_eye_base_240.copy()
    draw = ImageDraw.Draw(base)
    draw.ellipse((px - pupil_radius, py - pupil_radius, px + pupil_radius, py + pupil_radius), fill=(0, 0, 0))
    return base


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
    use_image = not EYES_SOLID_COLORS and not use_gradient and not use_rainbow and not use_animated and load_eye_image() is not None

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
            show_eye_image(left_eye)
            time.sleep(0.05)
            show_eye_image(right_eye)
        else:
            if left_eye:
                left_eye.fill(0xF800)
            if right_eye:
                right_eye.fill(0x001F)

    if use_animated:
        print("  Animated eyes (headless, no monitor). UDP: blink, look x/y.")
        # Sclera = background, iris = circular layer on top (per eye.svg / PI_Eyes). Cached once.
        cached_eye_base_240 = build_eye_base_sclera_iris()
        import random
        pupil_x, pupil_y = 0.0, 0.0
        target_x, target_y = 0.0, 0.0
        # Blink: open 2–5 s, then closed (one duration), then open. Draw: closing = outside-in, opening = inside-out.
        blink_phase = None  # None (open) | 'closed'
        blink_phase_start = 0.0
        draw_closed_outside_in = False  # first closed frame: refresh outside-in
        blit_open_bottom_to_top = False  # first open frame after blink: refresh inside-out
        next_auto_blink = time.monotonic() + random.uniform(2.0, 5.0)  # open 2–5 s between blinks
        next_dart = 0.0
        ANIM_FPS = 60
        frame_dt = 1.0 / ANIM_FPS
        PUPIL_EASE = 0.48
        BLINK_CLOSED_MS = 0.075   # 75 ms fully closed
        BLINK_DEBOUNCE_S = 0.2
        last_blink_end = 0.0
        last_look_time = 0.0

        def do_blink():
            nonlocal blink_phase, blink_phase_start, draw_closed_outside_in
            blink_phase = "closed"
            blink_phase_start = time.monotonic()
            draw_closed_outside_in = True

        while True:
            now = time.monotonic()
            # UDP
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
            except BlockingIOError:
                pass
            except json.JSONDecodeError:
                pass

            # Auto blink: stay open 2–5 s then run blink sequence
            if blink_phase is None and now >= next_auto_blink:
                do_blink()
                next_auto_blink = now + random.uniform(2.0, 5.0)

            # Advance blink phase: closed (BLINK_CLOSED_MS) -> open
            elapsed = now - blink_phase_start
            if blink_phase == "closed" and elapsed >= BLINK_CLOSED_MS:
                blink_phase = None
                next_auto_blink = now + random.uniform(2.0, 5.0)
                blit_open_bottom_to_top = True  # first open frame: draw inside-out

            # Map phase to visual state for render
            blink_state = "open" if blink_phase is None else "closed"

            # Nervous dart: when idle (no recent UDP look), pick new random target often
            if now >= next_dart and (now - last_look_time) > 0.2:
                target_x = random.uniform(-0.85, 0.85)
                target_y = random.uniform(-0.85, 0.85)
                next_dart = now + random.uniform(0.06, 0.22)
            # Ease pupil toward target (fast for dart)
            pupil_x += (target_x - pupil_x) * PUPIL_EASE
            pupil_y += (target_y - pupil_y) * PUPIL_EASE
            pupil_x = max(-1.0, min(1.0, pupil_x))
            pupil_y = max(-1.0, min(1.0, pupil_y))

            # Eye layer: open eye (sclera + iris + pupil). Top-down normally; inside_out on first frame after blink (lid opens from center).
            eye_frame = render_animated_frame(cached_eye_base_240, pupil_x, pupil_y, "open")
            if blit_open_bottom_to_top:
                _blit_pil_to_both(eye_frame, reverse_rows=False, outside_in=False, inside_out=True, partial_rows=None)
                blit_open_bottom_to_top = False
            else:
                _blit_pil_to_both(eye_frame, reverse_rows=False, outside_in=False, inside_out=False, partial_rows=None)

            # Blink layer: separate overlay (black + eyelid line). outside_in when closing (first closed frame).
            if blink_state == "closed":
                overlay = render_blink_overlay()
                if overlay is not None:
                    _blit_pil_to_both(overlay, reverse_rows=False, outside_in=draw_closed_outside_in, inside_out=False, partial_rows=None)
                if draw_closed_outside_in:
                    draw_closed_outside_in = False
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

    def do_blink():
        for disp in (left_eye, right_eye):
            if disp:
                disp.fill(0x0000)
        time.sleep(0.05)
        restore_idle()

    BLINK_DEBOUNCE_S = 0.25
    last_blink_end = 0.0

    while True:
        try:
            data, _ = sock.recvfrom(1024)
            msg = json.loads(data.decode())
            action = msg.get("action")
            if action == "blink":
                now = time.monotonic()
                if now - last_blink_end < BLINK_DEBOUNCE_S:
                    pass
                else:
                    do_blink()
                    last_blink_end = time.monotonic()
                    print("🐾 Logic: Blinked both eyes.")
            elif action == "look":
                pass
        except BlockingIOError:
            pass
        except json.JSONDecodeError:
            pass
        time.sleep(0.01)


if __name__ == "__main__":
    run_eyes()
