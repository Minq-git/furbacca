"""
Eye shape masks: layer above sclera/iris/pupil that defines the visible eye outline.
Pixels outside the shape are black; inside the shape the eye content is shown.
Shapes: round, sharp, half_moon, bean, oval, trapezoid, tilted, dome, pill.
"""
import math

try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    Image = ImageDraw = None

import config

_mask_cache = {}  # (shape_name, size) -> PIL Image "L"


def _oval_bbox(size):
    """Same width as our oval (classic oval): slightly flatter ellipse."""
    margin_y = int(size * 0.08)
    return [0, margin_y, size - 1, size - 1 - margin_y]


def _sharp_points(size):
    """
    Sharp 'Cat Eye': Asymmetrical shape using Quadratic Bezier curves.
    - Inner corner: Lower, slightly rounded.
    - Outer corner: Higher, sharp (creates the tilt).
    - Top lid: High arch.
    - Bottom lid: Flatter curve.
    """
    pts = []
    
    # --- Configuration (0.0 to 1.0 relative to size) ---
    # Left Corner (Inner Eye) - positioned lower
    p_left = (0.10, 0.75) 
    
    # Right Corner (Outer Eye) - positioned higher and sharp
    p_right = (0.95, 0.35)
    
    # Top Control Point - pulls the bottom eyelid up high
    p_top_ctrl = (.25, -0.15) 
    
    # Bottom Control Point - gently curves the top eyelid
    p_bottom_ctrl = (0.50, 1.05)

    # --- Bezier Helper Function ---
    def get_bezier_point(t, start, control, end):
        # Formula: (1-t)^2 * P0 + 2(1-t)t * P1 + t^2 * P2
        x = (1 - t)**2 * start[0] + 2 * (1 - t) * t * control[0] + t**2 * end[0]
        y = (1 - t)**2 * start[1] + 2 * (1 - t) * t * control[1] + t**2 * end[1]
        return (int(x * size), int(y * size))

    # --- Generate Points ---
    steps = 20 # Higher number = smoother curve
    
    # 1. Top Lid: Draw from Left to Right
    for i in range(steps + 1):
        t = i / steps
        pts.append(get_bezier_point(t, p_left, p_top_ctrl, p_right))
        
    # 2. Bottom Lid: Draw from Right to Left (to close the loop)
    for i in range(steps + 1):
        t = i / steps
        # Note: start=p_right, end=p_left
        pts.append(get_bezier_point(t, p_right, p_bottom_ctrl, p_left))

    return pts


def _bean_points(size):
    """
    Bean (Inverted): Kidney shape with the 'dip' on top.
    - Sides are pulled UP (negative Y) relative to the center.
    - Result: Concave top, Convex bottom (like a smile).
    """
    pts = []
    cx, cy = size // 2, size // 2
    
    # 1. Dimensions
    w = size * 0.45  # Width
    h = size * 0.25  # Height
    
    # 2. Bend Factor
    # Determines how high the corners are pulled up.
    bend = size * 0.20 

    steps = 30
    for i in range(steps):
        angle = math.radians(i * 360 / steps)
        
        x_offset = w * math.cos(angle)
        y_offset = h * math.sin(angle)
        
        # Calculate the parabolic bend
        norm_x = x_offset / w
        y_bend_offset = bend * (norm_x ** 2)
        
        # SUBTRACT the bend to pull sides UP (Negative Y direction)
        final_x = cx + x_offset
        final_y = cy + y_offset - y_bend_offset 
        
        pts.append((int(final_x), int(final_y)))
        
    return pts


def get_shape_mask(shape_name, size=None):
    """
    Return a PIL Image (mode "L"): 255 inside the eye shape, 0 outside.
    Cached by (shape_name, size).
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
    cx, cy = size // 2, size // 2

    if shape_name == "round":
        draw.ellipse([0, 0, size - 1, size - 1], fill=255)
    elif shape_name == "oval":
        draw.ellipse(_oval_bbox(size), fill=255)
    elif shape_name == "pill":
        # Pill: tall and narrow (elongated vertically)
        margin_x = int(size * 0.18)
        margin_y = int(size * 0.05)
        draw.ellipse([margin_x, margin_y, size - 1 - margin_x, size - 1 - margin_y], fill=255)
    elif shape_name == "sharp":
        # Horizontal, smooth curved lids, sharp pointed corners (reference image)
        draw.polygon(_sharp_points(size), fill=255)
    elif shape_name == "half_moon":
        # Half-moon as seen on display: flat top, rounded bottom (mask = top half of circle; display is upside down)
        draw.ellipse([0, 0, size - 1, size - 1], fill=255)
        draw.rectangle([0, cy, size, size], fill=0)
    elif shape_name == "bean":
        # Kidney/lima: wider than tall, convex top, smooth concave dip on bottom (reference image)
        draw.polygon(_bean_points(size), fill=255)
    elif shape_name == "trapezoid":
        # Angular, straight lines; top wider than bottom
        pts = [
            (int(size * 0.18), int(size * 0.18)),
            (int(size * 0.82), int(size * 0.18)),
            (int(size * 0.88), int(size * 0.82)),
            (int(size * 0.12), int(size * 0.82)),
        ]
        draw.polygon(pts, fill=255)
    elif shape_name == "tilted":
        # Oval rotated (inner corner lower, outer higher)
        pad = int(size * 0.4)
        big = size + 2 * pad
        tmp = Image.new("L", (big, big), 0)
        d = ImageDraw.Draw(tmp)
        margin_y = int(size * 0.08)
        d.ellipse([pad, pad + margin_y, pad + size - 1, pad + size - 1 - margin_y], fill=255)
        resample = getattr(Image, "Resampling", Image).BICUBIC if hasattr(Image, "Resampling") else Image.BICUBIC
        tilted = tmp.rotate(-18, resample=resample)
        # Crop center size×size (rotate uses image center by default)
        x0 = (tilted.size[0] - size) // 2
        y0 = (tilted.size[1] - size) // 2
        mask.paste(tilted.crop((x0, y0, x0 + size, y0 + size)), (0, 0))
    elif shape_name == "dome":
        # Dome as seen on display: high arched top, flat bottom (mask = bottom half of circle; display is upside down)
        draw.ellipse([0, 0, size - 1, size - 1], fill=255)
        draw.rectangle([0, 0, size, cy], fill=0)
    else:
        draw.ellipse([0, 0, size - 1, size - 1], fill=255)
    _mask_cache[key] = mask
    return mask


def apply_shape_mask(frame, shape_name=None, mirror=False):
    """
    Apply the eye shape mask on top of the frame: inside shape = frame pixel, outside = black.
    mirror=True: flip the shape horizontally (for right eye so shapes mirror left/right).
    Returns new PIL Image RGB.
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
    if mirror:
        mask = mask.transpose(Image.FLIP_LEFT_RIGHT)
    black = Image.new("RGB", frame.size, (0, 0, 0))
    return Image.composite(frame, black, mask)
