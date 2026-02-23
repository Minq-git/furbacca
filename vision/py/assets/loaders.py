"""
Load eye assets from vision/py/assets/graphics (PIL): iris, sclera, single-eye image. Cached per type.
"""

from __future__ import annotations

import os

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    Image = None  # type: ignore[misc, assignment]

from . import config

_vision_dir = os.path.dirname(os.path.abspath(__file__))
_eye_image_pil: object | None = None
_sclera_by_type: dict[str, object] = {}
_iris_by_type: dict[str, object] = {}


def graphics_dir() -> str:
    return os.path.join(_vision_dir, "graphics")


def load_eye_image() -> object | None:
    """Load 240x240 image from vision/py/assets/graphics/ (PIL). Fallback for static/non-animated mode."""
    global _eye_image_pil
    if _eye_image_pil is not None:
        return _eye_image_pil
    if not HAS_PIL:
        return None
    gdir = graphics_dir()
    for name in ("eye.png", "eye.jpg", "iris.png", "iris.jpg", "sclera.png", "dragon-iris.jpg"):
        path = os.path.join(gdir, name)
        if os.path.isfile(path):
            try:
                img = Image.open(path).convert("RGB")
                resampling = getattr(Image, "Resampling", Image)
                resample = getattr(resampling, "LANCZOS", 1)
                img = img.resize((config.EYE_SIZE, config.EYE_SIZE), resample)
                _eye_image_pil = img
                return _eye_image_pil
            except Exception as e:
                print(f"⚠ Could not load {path}: {e}")
    return None


def load_sclera_image(eye_type: str | None = None) -> object | None:
    """Load sclera texture (background / white of eye). Cached per type."""
    global _sclera_by_type
    if eye_type is None:
        eye_type = config.get_eye_type()
    if eye_type in _sclera_by_type:
        return _sclera_by_type[eye_type]
    if not HAS_PIL:
        return None
    gdir = graphics_dir()
    names = ("dragon-sclera.png",) if eye_type in ("dragon", "demon") else ("sclera.png",)
    for name in names:
        path = os.path.join(gdir, name)
        if os.path.isfile(path):
            try:
                img = Image.open(path).convert("RGB")
                resampling = getattr(Image, "Resampling", Image)
                resample = getattr(resampling, "LANCZOS", 1)
                img = img.resize((config.EYE_SIZE, config.EYE_SIZE), resample)
                _sclera_by_type[eye_type] = img
                return img
            except Exception as e:
                print(f"⚠ Could not load sclera {path}: {e}")
    return None


def load_iris_image(eye_type: str | None = None) -> object | None:
    """Load iris texture (colored ring). Cached per type."""
    global _iris_by_type
    if eye_type is None:
        eye_type = config.get_eye_type()
    if eye_type in _iris_by_type:
        return _iris_by_type[eye_type]
    if not HAS_PIL:
        return None
    gdir = graphics_dir()
    names = ("dragon-iris.jpg",) if eye_type in ("dragon", "demon") else ("iris.png", "iris.jpg")
    for name in names:
        path = os.path.join(gdir, name)
        if os.path.isfile(path):
            try:
                img = Image.open(path).convert("RGB")
                resampling = getattr(Image, "Resampling", Image)
                resample = getattr(resampling, "LANCZOS", 1)
                img = img.resize((config.EYE_SIZE, config.EYE_SIZE), resample)
                _iris_by_type[eye_type] = img
                return img
            except Exception as e:
                print(f"⚠ Could not load iris {path}: {e}")
    return None
