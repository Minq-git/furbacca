"""
Preset eye animations. Each animation is a list of segments.
Segment format: (duration_sec, target_x, target_y) or (duration_sec, target_x, target_y, pupil_mode).
target_x, target_y in [-1, 1]. pupil_mode optional: "wide" | "focused" | "relaxed" (overrides normal pupil size for that segment).
"""
import random


def get_animation(name, **kwargs):
    """
    Return list of segments for the named animation, or [] if unknown.
    name: e.g. "nervous_look", "shiver"
    kwargs: optional overrides (e.g. n_repeats for nervous_look).
    """
    name = (name or "").strip().lower()
    if name == "nervous_look":
        return _nervous_look(**kwargs)
    if name == "shiver":
        return _shiver()
    return []


def _shiver():
    """
    Short pupil jiggle (e.g. from SW-420 vibration / Matter.js impulse).
    Small fast x/y offsets then back to centre.
    """
    return [
        (0.04, 0.22, 0.0),
        (0.04, -0.18, 0.04),
        (0.04, 0.14, -0.04),
        (0.04, -0.08, 0.0),
        (0.06, 0.0, 0.0),
    ]


def _nervous_look(n_repeats=None):
    """
    Look left/right with focused pupils, then re-centre and go wide, then relaxed.
    n_repeats: number of left-right cycles (default random 2–3).
    """
    if n_repeats is None:
        n_repeats = random.randint(2, 3)
    n_repeats = max(1, min(5, int(n_repeats)))
    # Focused pupils while looking left and right
    segments = []
    for _ in range(n_repeats):
        segments.append((0.28, -1.0, 0.0, "focused"))   # look left
        segments.append((0.28, 1.0, 0.0, "focused"))     # look right
    # Re-centre, then relax
    segments.append((0.9, 0.0, 0.0, "relaxed"))        # move to centre, back to normal
    return segments
