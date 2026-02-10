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
    for name in ("eye.png", "eye.jpg", "iris.jpg", "sclera.png", "dragon-iris.jpg"):
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
    """Write buffer (row or full frame) to /dev/fb1. Same format as test-fb1-gradient.py (LE RGB565). Needs sudo for /dev/fb1."""
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
    """Draw eye image to /dev/fb1 (left eye when overlay is used). Same format as test-fb1-gradient.py."""
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

def show_eye_image(display):
    """Send PIL image to gc9a01py display. SPI typically expects big-endian (>H); if colors look inverted, try <H."""
    img = load_eye_image()
    if img is None or display is None:
        return
    try:
        import struct
        # gc9a01py / raw SPI usually expects big-endian RGB565; framebuffer overlay uses little-endian (<H)
        PACK_FMT = ">H"
        img = img.rotate(180)
        row_buf = bytearray(EYE_SIZE * 2)
        for y in range(EYE_SIZE):
            for x in range(EYE_SIZE):
                r, g, b = img.getpixel((x, y))
                c565 = (r & 0xF8) << 8 | (g & 0xFC) << 3 | (b >> 3)
                row_buf[x * 2 : x * 2 + 2] = struct.pack(PACK_FMT, c565)
            display.blit_buffer(row_buf, 0, y, EYE_SIZE, 1)
    except Exception as e:
        print(f"⚠ Show image error: {e}")


def run_eyes():
    if left_eye is None and right_eye is None:
        print("❌ No displays initialized. Run scripts/fetch-gc9a01py.sh and ensure vision/machine_compat and vision/gc9a01py are present.")
        return

    print("👀 Furbacca Vision Online (gc9a01py).")
    use_image = not EYES_SOLID_COLORS and load_eye_image() is not None
    if use_image:
        print("  Showing eye image on both displays...")
        show_eye_image(left_eye)
        time.sleep(0.02)
        show_eye_image(right_eye)
    else:
        if EYES_SOLID_COLORS:
            print("  Solid colors only (EYES_SOLID_COLORS=1).")
        if left_eye:
            left_eye.fill(0xF800)
        time.sleep(0.02)
        if right_eye:
            right_eye.fill(0x001F)

    def restore_idle():
        if use_image:
            show_eye_image(left_eye)
            time.sleep(0.02)
            show_eye_image(right_eye)
        else:
            if left_eye:
                left_eye.fill(0xF800)
            if right_eye:
                right_eye.fill(0x001F)

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
