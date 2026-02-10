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


def _blit_buffer_row_by_row_both(buf, reverse_rows=False, outside_in=False, inside_out=False):
    """Blit same buffer row-by-row. outside_in=edges toward center (closing); inside_out=center toward edges (opening)."""
    if buf is None:
        return
    if outside_in:
        # Closing: draw from both ends toward center: 239, 0, 238, 1, 237, 2, ...
        ys = []
        for i in range(EYE_SIZE):
            if i % 2 == 0:
                ys.append(EYE_SIZE - 1 - (i // 2))
            else:
                ys.append(i // 2)
    elif inside_out:
        # Opening: draw from center toward top and bottom: 120, 119, 121, 118, 122, ...
        center = EYE_SIZE // 2
        ys = [center]
        for offset in range(1, center + 1):
            if center - offset >= 0:
                ys.append(center - offset)
            if center + offset < EYE_SIZE:
                ys.append(center + offset)
    elif reverse_rows:
        ys = range(EYE_SIZE - 1, -1, -1)
    else:
        ys = range(EYE_SIZE)
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


def _blit_pil_to_both(img, reverse_rows=False, outside_in=False, inside_out=False):
    """Blit same PIL image to both displays. outside_in=closing; inside_out=opening (center toward edges)."""
    if img is None:
        return
    buf = _pil_to_rgb565_be_buffer(img)
    _blit_buffer_row_by_row_both(buf, reverse_rows=reverse_rows, outside_in=outside_in, inside_out=inside_out)


def render_animated_frame(cached_iris_240, pupil_x, pupil_y, blink_state="open"):
    """
    Three visual states:
    - open: full eye (large circle)
    - half: horizontal oval slit (lidded)
    - closed: black with single horizontal line (eyelid line)
    """
    from PIL import ImageDraw
    import math
    cx, cy = EYE_SIZE // 2, EYE_SIZE // 2

    if blink_state == "closed":
        base = Image.new("RGB", (EYE_SIZE, EYE_SIZE), (0, 0, 0))
        draw = ImageDraw.Draw(base)
        line_y = cy
        for dy in (-1, 0, 1):
            draw.line([(0, line_y + dy), (EYE_SIZE, line_y + dy)], fill=(28, 28, 28), width=1)
        return base

    if cached_iris_240 is None:
        base = Image.new("RGB", (EYE_SIZE, EYE_SIZE), (32, 32, 48))
    else:
        base = cached_iris_240.copy()
    draw = ImageDraw.Draw(base)
    pupil_radius = 18
    px = int(cx + pupil_x * 35)
    py = int(cy + pupil_y * 35)
    draw.ellipse((px - pupil_radius, py - pupil_radius, px + pupil_radius, py + pupil_radius), fill=(0, 0, 0))

    if blink_state == "half":
        # Curved lids with edges further down (reversed curve): lid edge dips at sides.
        slit_half = 14
        edge_drop = 4   # lid edge at sides this many px lower than at center
        step = 6
        # Top lid: bottom edge at center y=106, at sides y=106+edge_drop (110)
        top_center_y = cy - slit_half
        top_edge_y = top_center_y + edge_drop
        top_cy = (top_center_y + top_edge_y) / 2.0
        top_radius = (top_edge_y - top_center_y) / 2.0
        top_arc = []
        for x in range(EYE_SIZE, -1, -step):
            t = (x - cx) / cx
            t = max(-1.0, min(1.0, t))
            y = top_cy - top_radius * math.sqrt(1.0 - t * t)  # center 106, edges 110 (lower)
            top_arc.append((x, int(y)))
        top_poly = [(0, 0), (EYE_SIZE, 0)] + top_arc[1:]
        draw.polygon(top_poly, fill=(0, 0, 0))
        # Bottom lid: top edge at center y=134, at sides y=134+edge_drop (138)
        bot_center_y = cy + slit_half
        bot_edge_y = bot_center_y + edge_drop
        bot_cy = (bot_center_y + bot_edge_y) / 2.0
        bot_radius = (bot_edge_y - bot_center_y) / 2.0
        bot_arc = []
        for x in range(EYE_SIZE, -1, -step):
            t = (x - cx) / cx
            t = max(-1.0, min(1.0, t))
            y = bot_cy - bot_radius * math.sqrt(1.0 - t * t)  # center 134, edges 138 (lower)
            bot_arc.append((x, int(y)))
        bot_poly = [(0, EYE_SIZE), (EYE_SIZE, EYE_SIZE)] + bot_arc[1:]
        draw.polygon(bot_poly, fill=(0, 0, 0))

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
        # Blink: three states, fixed timings — Half (50ms) -> Closed (100ms) -> Half (50ms) -> Open
        blink_phase = None  # None | 'half_closing' | 'closed' | 'half_opening'
        blink_phase_start = 0.0
        blit_open_bottom_to_top = False  # set True on first open frame after blink; draw bottom-to-top so lid opens upward
        next_auto_blink = time.monotonic() + random.uniform(2.0, 5.0)  # open 2–5 s between blinks
        next_dart = 0.0
        ANIM_FPS = 55
        frame_dt = 1.0 / ANIM_FPS
        PUPIL_EASE = 0.48
        BLINK_HALF_MS = 0.35   # 350 ms half-closed (each side)
        BLINK_CLOSED_MS = 0.3  # 300 ms fully closed; total blink ~1 s
        BLINK_DEBOUNCE_S = 0.2
        last_blink_end = 0.0
        last_look_time = 0.0

        def do_blink():
            nonlocal blink_phase, blink_phase_start
            blink_phase = "half_closing"
            blink_phase_start = time.monotonic()

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

            # Advance blink phase: half_closing (50ms) -> closed (100ms) -> half_opening (50ms) -> open
            elapsed = now - blink_phase_start
            if blink_phase == "half_closing" and elapsed >= BLINK_HALF_MS:
                blink_phase = "closed"
                blink_phase_start = now
            elif blink_phase == "closed" and elapsed >= BLINK_CLOSED_MS:
                blink_phase = "half_opening"
                blink_phase_start = now
                blit_open_bottom_to_top = True  # partially open frame: draw bottom-to-top so lid opens upward
            elif blink_phase == "half_opening" and elapsed >= BLINK_HALF_MS:
                blink_phase = None
                next_auto_blink = now + random.uniform(2.0, 5.0)
                blit_open_bottom_to_top = True  # next frame = first open; draw bottom-to-top so lid appears to open upward

            # Map phase to visual state for render
            if blink_phase is None:
                blink_state = "open"
            elif blink_phase == "closed":
                blink_state = "closed"
            else:
                blink_state = "half"

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

            frame = render_animated_frame(cached_iris_240, pupil_x, pupil_y, blink_state)
            # Closing: outside_in (half_closing). Opening: inside_out (half_opening + first open frame).
            opening = (blink_state == "half" and blink_phase == "half_opening") or blit_open_bottom_to_top
            _blit_pil_to_both(frame, reverse_rows=False, outside_in=(blink_state == "half" and blink_phase == "half_closing"), inside_out=opening)
            if blit_open_bottom_to_top:
                blit_open_bottom_to_top = False
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
