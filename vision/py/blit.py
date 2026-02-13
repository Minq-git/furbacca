"""
RGB565 packing and blit to one or both GC9A01 displays. One byte order for all (big-endian).
NumPy path is much faster (15–30 FPS). If you see a blue tint with NumPy, set EYES_NUMPY_SWAP_RB=1.
"""
import os
import struct

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
# Force fallback (slower, correct colors) when NumPy path gives wrong colors despite channel check.
_USE_NUMPY_BLIT = os.environ.get("EYES_USE_NUMPY_BLIT", "1").strip().lower() not in ("0", "false", "no")


def rgb565(r, g, b):
    """Pack R,G,B (0-255) to RGB565 for GC9A01 (big-endian). Used for eye image, gradient, rainbow."""
    c565 = (r & 0xF8) << 8 | (g & 0xFC) << 3 | (b >> 3)
    return struct.pack(">H", c565)


def _pil_to_rgb565_numpy(img):
    """Fast path: whole-image RGB565 via NumPy. Exact fallback masking + uint16 promotion (avoids blue tint from bit-promotion)."""
    arr = np.array(img, dtype=np.uint8)
    arr = np.flip(arr, axis=(0, 1)).copy()  # rotate 180 (GC9A01 orientation)
    if _NUMPY_SWAP_RB:
        r = arr[:, :, 2].astype(np.uint16)
        g = arr[:, :, 1].astype(np.uint16)
        b = arr[:, :, 0].astype(np.uint16)
    else:
        r = arr[:, :, 0].astype(np.uint16)
        g = arr[:, :, 1].astype(np.uint16)
        b = arr[:, :, 2].astype(np.uint16)
    # Same logic as fallback: mask first so no garbage bits shift into other channels
    rgb565_u16 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return rgb565_u16.astype(">u2").tobytes()


def _pil_to_rgb565_fallback(img):
    """Fallback when NumPy missing: direct pixel access (same output as NumPy path when SWAP_RB correct)."""
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


def pil_to_rgb565_buffer(img):
    """Convert 240x240 PIL RGB to bytearray RGB565 (row-major). Uses NumPy when available for 15–30 FPS."""
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


def blit_buffer_row_by_row(display, buf):
    """Blit RGB565 buffer to display row-by-row."""
    if display is None or buf is None:
        return
    for y in range(EYE_SIZE):
        display.blit_buffer(buf[y * EYE_SIZE * 2 : (y + 1) * EYE_SIZE * 2], 0, y, EYE_SIZE, 1)


def blit_buffer_full_frame_both(left_eye, right_eye, buf):
    """Blit full 240x240 buffer to both displays in one call per display."""
    if buf is None or len(buf) < EYE_SIZE * EYE_SIZE * 2:
        return
    if left_eye is not None:
        left_eye.blit_buffer(buf, 0, 0, EYE_SIZE, EYE_SIZE)
    if right_eye is not None:
        right_eye.blit_buffer(buf, 0, 0, EYE_SIZE, EYE_SIZE)


def blit_buffer_row_by_row_both(left_eye, right_eye, buf_left, buf_right=None, reverse_rows=False, outside_in=False, inside_out=False, partial_rows=None):
    """Blit buffer(s) row-by-row. If buf_right is None, use buf_left for both. Otherwise left to left display, right to right (mirrored shapes)."""
    if buf_left is None:
        return
    if buf_right is None:
        buf_right = buf_left
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
        row_left = buf_left[y * EYE_SIZE * 2 : (y + 1) * EYE_SIZE * 2]
        row_right = buf_right[y * EYE_SIZE * 2 : (y + 1) * EYE_SIZE * 2]
        if left_eye is not None:
            left_eye.blit_buffer(row_left, 0, y, EYE_SIZE, 1)
        if right_eye is not None:
            right_eye.blit_buffer(row_right, 0, y, EYE_SIZE, 1)


def blit_pil_to_display(display, img):
    """Blit a 240x240 PIL RGB image to one display. RGB565 row-by-row (same as gradient/rainbow)."""
    if display is None or img is None:
        return
    buf = pil_to_rgb565_buffer(img)
    if buf:
        blit_buffer_row_by_row(display, buf)


def blit_pil_to_both(left_eye, right_eye, left_img, right_img=None, reverse_rows=False, outside_in=False, inside_out=False, partial_rows=None):
    """Blit PIL image(s) to both displays. If right_img is None, use left_img for both (no mirror). Otherwise left to left display, right to right (for mirrored shapes)."""
    if left_img is None:
        return
    if right_img is None:
        right_img = left_img
    buf_left = pil_to_rgb565_buffer(left_img)
    buf_right = pil_to_rgb565_buffer(right_img)
    if buf_left is None:
        return
    if buf_right is None:
        buf_right = buf_left
    if not reverse_rows and not outside_in and not inside_out and partial_rows is None:
        if left_eye is not None:
            left_eye.blit_buffer(buf_left, 0, 0, EYE_SIZE, EYE_SIZE)
        if right_eye is not None:
            right_eye.blit_buffer(buf_right, 0, 0, EYE_SIZE, EYE_SIZE)
    else:
        blit_buffer_row_by_row_both(left_eye, right_eye, buf_left, buf_right, reverse_rows=reverse_rows, outside_in=outside_in, inside_out=inside_out, partial_rows=partial_rows)
