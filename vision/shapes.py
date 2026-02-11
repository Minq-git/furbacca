"""
Eye shape masks: layer above sclera/iris/pupil that defines the visible eye outline.
Pixels outside the shape are black; inside the shape the eye content is shown.
"""
try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    Image = ImageDraw = None

import config

_mask_cache = {}  # (shape_name, size) -> PIL Image "L"


def get_shape_mask(shape_name, size=None):
    """
    Return a PIL Image (mode "L"): 255 inside the eye shape, 0 outside.
    Cached by (shape_name, size). shape_name: round, oval, almond.
    """
    if not HAS_PIL or size is None:
        size = config.EYE_SIZE
    shape_name = (shape_name or "round").strip().lower()
    if shape_name not in config.EYE_SHAPES:
        shape_name = "round"
    key = (shape_name, size)
    if key in _mask_cache:
        return _mask_cache[key]
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    # Bounding box [left, top, right, bottom] for ellipse
    if shape_name == "round":
        # Circle: full 240x240
        draw.ellipse([0, 0, size - 1, size - 1], fill=255)
    elif shape_name == "oval":
        # Ellipse: slightly flatter (wider than tall)
        margin_y = int(size * 0.08)
        draw.ellipse([0, margin_y, size - 1, size - 1 - margin_y], fill=255)
    elif shape_name == "almond":
        # Almond: more elongated vertically (narrower horizontally)
        margin_x = int(size * 0.18)
        margin_y = int(size * 0.05)
        draw.ellipse([margin_x, margin_y, size - 1 - margin_x, size - 1 - margin_y], fill=255)
    else:
        draw.ellipse([0, 0, size - 1, size - 1], fill=255)
    _mask_cache[key] = mask
    return mask


def apply_shape_mask(frame, shape_name=None):
    """
    Apply the eye shape mask on top of the frame: inside shape = frame pixel, outside = black.
    frame: PIL Image RGB, same size as mask. Returns new PIL Image RGB.
    """
    if frame is None or not HAS_PIL:
        return frame
    if shape_name is None:
        shape_name = config.get_eye_shape()
    size = frame.size[0]
    mask = get_shape_mask(shape_name, size)
    if mask.size != frame.size:
        resample = getattr(Image, "Resampling", Image).NEAREST if hasattr(Image, "Resampling") else Image.NEAREST
        mask = mask.resize(frame.size, resample)
    black = Image.new("RGB", frame.size, (0, 0, 0))
    return Image.composite(frame, black, mask)
