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


def load_eye_image():
    """Load 240x240 image from vision/graphics/ (PIL)."""
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


def _blit_pil_to_display(display, img):
    """Blit a 240x240 PIL RGB image to one display. Big-endian RGB565 row-by-row (same path as show_eye_image)."""
    if display is None or img is None:
        return
    buf = _pil_to_rgb565_be_buffer(img)
    _blit_buffer_row_by_row(display, buf)


def _blit_pil_to_both(img):
    """Blit same PIL image to both displays. One buffer, row-by-row blits (same path as static image)."""
    if img is None:
        return
    buf = _pil_to_rgb565_be_buffer(img)
    if left_eye is not None:
        _blit_buffer_row_by_row(left_eye, buf)
    if right_eye is not None:
        _blit_buffer_row_by_row(right_eye, buf)


def render_animated_frame(cached_iris_240, pupil_x, pupil_y, blink_close_ratio=0.0):
    """Render one 240x240 frame. cached_iris_240 = pre-sized RGB 240x240 (no resize per frame). Pupil -1..1, blink 0=open 1=closed."""
    if cached_iris_240 is None:
        base = Image.new("RGB", (EYE_SIZE, EYE_SIZE), (32, 32, 48))
    else:
        base = cached_iris_240.copy()
    if blink_close_ratio >= 0.99:
        return Image.new("RGB", (EYE_SIZE, EYE_SIZE), (0, 0, 0))
    cx, cy = EYE_SIZE // 2, EYE_SIZE // 2
    pupil_radius = 18
    px = int(cx + pupil_x * 35)
    py = int(cy + pupil_y * 35)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(base)
    draw.ellipse((px - pupil_radius, py - pupil_radius, px + pupil_radius, py + pupil_radius), fill=(0, 0, 0))
    if blink_close_ratio > 0.01:
        h = int(EYE_SIZE * blink_close_ratio * 0.55)
        draw.rectangle((0, 0, EYE_SIZE, h), fill=(0, 0, 0))
        draw.rectangle((0, EYE_SIZE - h, EYE_SIZE, EYE_SIZE), fill=(0, 0, 0))
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
    use_animated = EYES_ANIMATED and HAS_PIL and load_eye_image() is not None
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
        raw_iris = load_eye_image()
        # Cache 240x240 RGB once (no resize per frame); avoids static and speeds up render.
        cached_iris_240 = None
        if raw_iris is not None:
            if raw_iris.mode != "RGB":
                raw_iris = raw_iris.convert("RGB")
            cached_iris_240 = raw_iris.resize((EYE_SIZE, EYE_SIZE), getattr(Image, "Resampling", Image).LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS)
        import random
        pupil_x, pupil_y = 0.0, 0.0
        target_x, target_y = 0.0, 0.0
        blink_until = 0.0
        blink_close = 0.0
        next_auto_blink = time.monotonic() + random.uniform(2.0, 5.0)
        ANIM_FPS = 30
        frame_dt = 1.0 / ANIM_FPS
        PUPIL_EASE = 0.12
        BLINK_DURATION = 0.12
        BLINK_DEBOUNCE_S = 0.25
        last_blink_end = 0.0

        def do_blink():
            nonlocal blink_until, blink_close
            blink_until = time.monotonic() + BLINK_DURATION
            blink_close = 1.0

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
            except BlockingIOError:
                pass
            except json.JSONDecodeError:
                pass

            # Auto blink
            if now >= next_auto_blink and blink_until <= now:
                do_blink()
                next_auto_blink = now + random.uniform(2.0, 5.0)

            # Blink state
            if blink_until > now:
                elapsed = BLINK_DURATION - (blink_until - now)
                if elapsed < BLINK_DURATION * 0.4:
                    blink_close = elapsed / (BLINK_DURATION * 0.4)
                else:
                    blink_close = (BLINK_DURATION - elapsed) / (BLINK_DURATION * 0.6)
                    blink_close = max(0.0, min(1.0, blink_close))
            else:
                blink_close = 0.0

            # Ease pupil toward target + idle drift
            pupil_x += (target_x - pupil_x) * PUPIL_EASE + random.uniform(-0.02, 0.02)
            pupil_y += (target_y - pupil_y) * PUPIL_EASE + random.uniform(-0.02, 0.02)
            pupil_x = max(-1.0, min(1.0, pupil_x))
            pupil_y = max(-1.0, min(1.0, pupil_y))

            frame = render_animated_frame(cached_iris_240, pupil_x, pupil_y, blink_close)
            _blit_pil_to_both(frame)
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
