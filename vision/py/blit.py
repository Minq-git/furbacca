"""
RGB565 packing and blit to one or both GC9A01 displays. One byte order for all (big-endian).
NumPy path is much faster (15–30 FPS). If you see a blue tint with NumPy, set EYES_NUMPY_SWAP_RB=1.
Double-buffer: async worker thread does blocking SPI so the main loop can render the next frame.
"""
import os
import queue
import struct
import threading

try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    np = None
    _HAS_NUMPY = False

import config

EYE_SIZE = config.EYE_SIZE

# On some Pi/PIL setups np.array(img) is BGR; swap so we pack correct RGB565 (fixes blue tint).
_NUMPY_SWAP_RB = os.environ.get("EYES_NUMPY_SWAP_RB", "").strip().lower() in ("1", "true", "yes")
_USE_NUMPY_BLIT = os.environ.get("EYES_USE_NUMPY_BLIT", "1").strip().lower() not in ("0", "false", "no")

# Async blit: depth 1 so we only care about the most recent frame; drops older pending frame if full.
_blit_queue = queue.Queue(maxsize=1)

def _blit_worker():
    """Background thread: processes both eyes as a single atomic task."""
    while True:
        task = _blit_queue.get()
        if task is None:
            break
        
        l_handle, l_buf, r_handle, r_buf = task
        
        try:
            # Shared SPI bus: these MUST happen sequentially
            if l_handle and l_buf:
                l_handle.blit_buffer(l_buf, 0, 0, EYE_SIZE, EYE_SIZE)
            if r_handle and r_buf:
                r_handle.blit_buffer(r_buf, 0, 0, EYE_SIZE, EYE_SIZE)
        except Exception as e:
            print(f"SPI Worker Error: {e}")
        finally:
            _blit_queue.task_done()

_worker_thread = threading.Thread(target=_blit_worker, daemon=True)
_worker_thread.start()

def blit_pil_to_both_async(left_eye, right_eye, left_img, right_img=None, reverse_rows=False, outside_in=False, inside_out=False, partial_rows=None):
    """Atomic async handoff of both eyes to the worker thread."""
    if left_img is None:
        return

    # Fallback to sync for special row animations
    if reverse_rows or outside_in or inside_out or partial_rows is not None:
        blit_pil_to_both(left_eye, right_eye, left_img, right_img, reverse_rows, outside_in, inside_out, partial_rows)
        return

    # Generate buffers
    buf_left = pil_to_rgb565_buffer(left_img)
    if buf_left is None:
        return
        
    actual_right = right_img if right_img is not None else left_img
    buf_right = pil_to_rgb565_buffer(actual_right)
    if buf_right is None:
        buf_right = buf_left

    # Atomic Task Handoff
    try:
        if _blit_queue.full():
            try:
                _blit_queue.get_nowait()
            except queue.Empty:
                pass
        _blit_queue.put_nowait((left_eye, buf_left, right_eye, buf_right))
    except queue.Full:
        pass

def _pil_to_rgb565_numpy(img):
    """Fast path: whole-image RGB565 via NumPy without redundant copies."""
    arr = np.array(img, dtype=np.uint8)
    flipped_view = np.flip(arr, axis=(0, 1))
    
    if _NUMPY_SWAP_RB:
        r = flipped_view[:, :, 2].astype(np.uint16)
        g = flipped_view[:, :, 1].astype(np.uint16)
        b = flipped_view[:, :, 0].astype(np.uint16)
    else:
        r = flipped_view[:, :, 0].astype(np.uint16)
        g = flipped_view[:, :, 1].astype(np.uint16)
        b = flipped_view[:, :, 2].astype(np.uint16)

    rgb565_u16 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return rgb565_u16.astype(">u2").tobytes()

def pil_to_rgb565_buffer(img):
    """Convert PIL RGB to RGB565 buffer."""
    if img is None or PILImage is None:
        return None
    if img.mode != "RGB":
        img = img.convert("RGB")
    if img.size != (EYE_SIZE, EYE_SIZE):
        resample = getattr(PILImage, "Resampling", PILImage).LANCZOS if hasattr(PILImage, "Resampling") else PILImage.LANCZOS
        img = img.resize((EYE_SIZE, EYE_SIZE), resample)
        
    if _HAS_NUMPY and _USE_NUMPY_BLIT:
        return _pil_to_rgb565_numpy(img)
    return _pil_to_rgb565_fallback(img)

def _pil_to_rgb565_fallback(img):
    """Slow fallback without NumPy."""
    img = img.rotate(180)
    pix = img.load()
    buf = bytearray(EYE_SIZE * EYE_SIZE * 2)
    for y in range(EYE_SIZE):
        for x in range(EYE_SIZE):
            r, g, b = pix[x, y]
            c565 = (r & 0xF8) << 8 | (g & 0xFC) << 3 | (b >> 3)
            offset = (y * EYE_SIZE + x) * 2
            buf[offset : offset + 2] = struct.pack(">H", c565)
    return buf

def blit_pil_to_both(left_eye, right_eye, left_img, right_img=None, reverse_rows=False, outside_in=False, inside_out=False, partial_rows=None):
    """Synchronous blit for special animations or initialization."""
    if left_img is None:
        return
    buf_left = pil_to_rgb565_buffer(left_img)
    if buf_left is None:
        return
    actual_right = right_img if right_img is not None else left_img
    buf_right = pil_to_rgb565_buffer(actual_right)
    if buf_right is None:
        buf_right = buf_left
        
    if not reverse_rows and not outside_in and not inside_out and partial_rows is None:
        if left_eye is not None:
            left_eye.blit_buffer(buf_left, 0, 0, EYE_SIZE, EYE_SIZE)
        if right_eye is not None:
            right_eye.blit_buffer(buf_right, 0, 0, EYE_SIZE, EYE_SIZE)
    else:
        blit_buffer_row_by_row_both(left_eye, right_eye, buf_left, buf_right, reverse_rows, outside_in, inside_out, partial_rows)

def _row_order_outside_in():
    """Row indices top→bottom then bottom→top so lids appear to close from edges toward center."""
    order = []
    for i in range((EYE_SIZE + 1) // 2):
        order.append(i)
        if EYE_SIZE - 1 - i != i:
            order.append(EYE_SIZE - 1 - i)
    return order


def _row_order_inside_out():
    """Row indices center outward for opening (reverse of outside_in)."""
    order = _row_order_outside_in()
    return order[::-1]


def blit_buffer_row_by_row_both(left_eye, right_eye, buf_left, buf_right, reverse_rows=False, outside_in=False, inside_out=False, partial_rows=None):
    """Blit buffer row-by-row for organic blink: outside_in = close from edges; inside_out = open from center."""
    row_bytes = EYE_SIZE * 2
    if outside_in:
        order = _row_order_outside_in()
    elif inside_out:
        order = _row_order_inside_out()
    elif reverse_rows:
        order = list(range(EYE_SIZE - 1, -1, -1))
    else:
        order = list(range(EYE_SIZE))
    if partial_rows is not None:
        order = [y for y in order if y in partial_rows]
    for y in order:
        start = y * row_bytes
        row_left = buf_left[start : start + row_bytes]
        row_right = buf_right[start : start + row_bytes]
        if left_eye is not None and row_left:
            left_eye.blit_buffer(row_left, 0, y, EYE_SIZE, 1)
        if right_eye is not None and row_right:
            right_eye.blit_buffer(row_right, 0, y, EYE_SIZE, 1)