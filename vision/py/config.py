"""
Vision constants and eye-type configuration (env flags, get/set eye type, scales, pupil radii).
"""
import os

EYE_SIZE = 240
# Iris circle radius in pixels (from eye.svg: iris path radius 17.7 in 68px viewBox, eye radius 34)
IRIS_R = int((EYE_SIZE // 2) * 17.7 / 34)
# Eye layer drawn 25% larger than viewport so when the eye moves we don't see black edges
EYE_LAYER_VIEWPORT_SCALE = 1.25

# Env flags
SWAP_LEFT_RIGHT_SPI = os.environ.get("SWAP_LEFT_RIGHT_SPI", "").strip().lower() in ("1", "true", "yes")
EYES_SOLID_COLORS = os.environ.get("EYES_SOLID_COLORS", "").strip().lower() in ("1", "true", "yes")
EYES_GRADIENT = os.environ.get("EYES_GRADIENT", "").strip().lower() in ("1", "true", "yes")
EYES_RAINBOW = os.environ.get("EYES_RAINBOW", "").strip().lower() in ("1", "true", "yes")
EYES_ANIMATED = os.environ.get("EYES_ANIMATED", "1").strip().lower() not in ("0", "false", "no")

_eye_type_raw = os.environ.get("EYE_TYPE", "").strip().lower()
_current_eye_type = None  # None = use env default; set via set_eye_type() for runtime changes

EYE_TYPE_CYCLE = ("default", "human", "dragon", "demon")

# Build / cache (Option A / C)
EYE_GAZE_CACHE_STEP = 0.1
EYE_BUILD_SIZE = int(os.environ.get("EYE_BUILD_SIZE", "240"))  # 240 = full res; lower for faster builds

# --- Animated eyes: timing & motion (eyes.py loop) ---
ANIM_FPS = int(os.environ.get("ANIM_FPS", "30"))
EASE_TABLE_SIZE = 256
IDLE_LOOK_TIMEOUT_S = 0.2
MOVE_DURATION_MIN_S = 0.072
MOVE_DURATION_MAX_S = 0.144
HOLD_DURATION_MAX_S = 3.0
PUPIL_EASE_FACTOR = 0.48
FOCUS_HOLD_S = 0.35
PUPIL_TRANSITION_S = 0.5
PUPIL_TRANSITION_ANIM_S = 0.06
SHIVER_DEBOUNCE_S = 0.28
LOOK_CLAMP_MIN = -1.0
LOOK_CLAMP_MAX = 1.0
IDLE_WANDER_MIN = -0.8
IDLE_WANDER_MAX = 0.8
UDP_RECV_SIZE = 1024
SEGMENT_INDEX_NONE = -1

# Eye shape mask — layer above sclera/iris/pupil
_eye_shape_raw = os.environ.get("EYE_SHAPE", "round").strip().lower()
_current_eye_shape = None
EYE_SHAPES = (
    "round", 
    "sharp", 
    "half_moon", 
    "bean", 
    "concerned",
    "oval", 
    "tilted", 
    "dome", 
    "pill", 
    "heart", 
    "anime", 
    "glare", 
    "gemini", 
    "sus", 
    "stern", 
    "kawaii"
)

def get_eye_type():
    """Return current eye type (default, human, dragon, demon). Use set_eye_type() to change at runtime."""
    if _current_eye_type is not None:
        return _current_eye_type
    if _eye_type_raw in ("human", "dragon", "demon"):
        return _eye_type_raw
    return "default"


def set_eye_type(eye_type):
    """Set eye type at runtime. Pass 'default', 'human', 'dragon', or 'demon'; or None to reset to env default."""
    global _current_eye_type
    if eye_type is None:
        _current_eye_type = None
        return
    eye_type = str(eye_type).strip().lower()
    if eye_type in ("human", "dragon", "demon"):
        _current_eye_type = eye_type
    else:
        _current_eye_type = "default"


def cycle_eye_type():
    """Cycle to next eye type (default -> human -> dragon -> demon -> default). Returns new type."""
    current = get_eye_type()
    idx = EYE_TYPE_CYCLE.index(current) if current in EYE_TYPE_CYCLE else 0
    next_type = EYE_TYPE_CYCLE[(idx + 1) % len(EYE_TYPE_CYCLE)]
    set_eye_type(next_type)
    return next_type


def eye_type_scales(eye_type):
    """Return (invert_v, iris_scale, sclera_scale) for the given eye type."""
    invert_v = eye_type in ("human", "dragon")
    iris_scale = 0.8 if eye_type in ("human", "dragon") else 1.0
    sclera_scale = 1.2 if eye_type in ("human", "demon") else 1.0
    return (invert_v, iris_scale, sclera_scale)


def eye_type_pupil_radii(eye_type):
    """Return (relaxed, focused, wide) pupil radius for the given eye type."""
    if eye_type in ("default", "dragon"):
        return (40, 12, 60)
    return (22, 12, 40)


def get_eye_shape():
    """Return current eye shape (round, sharp, half_moon, bean, oval, tilted, dome, pill). Layer above eye content; outside shape is black."""
    if _current_eye_shape is not None:
        return _current_eye_shape
    if _eye_shape_raw in EYE_SHAPES:
        return _eye_shape_raw
    return "round"


def set_eye_shape(shape_name):
    """Set eye shape at runtime. Pass 'round', 'oval', 'pill', etc.; or None to reset to env default."""
    global _current_eye_shape
    if shape_name is None:
        _current_eye_shape = None
        return
    shape_name = str(shape_name).strip().lower()
    _current_eye_shape = shape_name if shape_name in EYE_SHAPES else "round"


def cycle_eye_shape():
    """Cycle to next eye shape. Returns new shape."""
    current = get_eye_shape()
    idx = EYE_SHAPES.index(current) if current in EYE_SHAPES else 0
    next_shape = EYE_SHAPES[(idx + 1) % len(EYE_SHAPES)]
    set_eye_shape(next_shape)
    return next_shape
