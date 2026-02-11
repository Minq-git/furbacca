"""
RGB565 packing and blit to one or both GC9A01 displays. One byte order for all (big-endian).
"""
import struct

try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None

import config

EYE_SIZE = config.EYE_SIZE


def rgb565(r, g, b):
    """Pack R,G,B (0-255) to RGB565 for GC9A01 (big-endian). Used for eye image, gradient, rainbow."""
    c565 = (r & 0xF8) << 8 | (g & 0xFC) << 3 | (b >> 3)
    return struct.pack(">H", c565)


def pil_to_rgb565_buffer(img):
    """Convert 240x240 PIL RGB to bytearray RGB565 (row-major). Same pack as rgb565()."""
    if img is None or PILImage is None:
        return None
    if img.mode != "RGB":
        img = img.convert("RGB")
    if img.size != (EYE_SIZE, EYE_SIZE):
        resample = getattr(PILImage, "Resampling", PILImage).LANCZOS if hasattr(PILImage, "Resampling") else PILImage.LANCZOS
        img = img.resize((EYE_SIZE, EYE_SIZE), resample)
    img = img.rotate(180)
    buf = bytearray(EYE_SIZE * EYE_SIZE * 2)
    for y in range(EYE_SIZE):
        for x in range(EYE_SIZE):
            r, g, b = img.getpixel((x, y))
            offset = (y * EYE_SIZE + x) * 2
            buf[offset : offset + 2] = rgb565(r, g, b)
    return buf


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


def blit_buffer_row_by_row_both(left_eye, right_eye, buf, reverse_rows=False, outside_in=False, inside_out=False, partial_rows=None):
    """Blit same buffer row-by-row to both displays. partial_rows=(y0,y1)=only those rows."""
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


def blit_pil_to_display(display, img):
    """Blit a 240x240 PIL RGB image to one display. RGB565 row-by-row (same as gradient/rainbow)."""
    if display is None or img is None:
        return
    buf = pil_to_rgb565_buffer(img)
    if buf:
        blit_buffer_row_by_row(display, buf)


def blit_pil_to_both(left_eye, right_eye, img, reverse_rows=False, outside_in=False, inside_out=False, partial_rows=None):
    """Blit same PIL image to both displays. Full-frame top-down uses single blit per display."""
    if img is None:
        return
    buf = pil_to_rgb565_buffer(img)
    if buf is None:
        return
    if not reverse_rows and not outside_in and not inside_out and partial_rows is None:
        blit_buffer_full_frame_both(left_eye, right_eye, buf)
    else:
        blit_buffer_row_by_row_both(left_eye, right_eye, buf, reverse_rows=reverse_rows, outside_in=outside_in, inside_out=inside_out, partial_rows=partial_rows)
