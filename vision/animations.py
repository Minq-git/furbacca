"""
Preset eye animations. Each animation is a list of segments.
Segment format: (duration_sec, target_x, target_y) or (duration_sec, target_x, target_y, pupil_mode).
target_x, target_y in [-1, 1]. pupil_mode optional: "wide" | "focused" | "relaxed" (overrides normal pupil size for that segment).
"""
import random


def get_animation(name, **kwargs):
    """
    Return list of segments for the named animation, or [] if unknown.
    name: e.g. "nervous_look"
    kwargs: optional overrides (e.g. n_repeats for nervous_look).
    """
    name = (name or "").strip().lower()
    if name == "nervous_look":
        return _nervous_look(**kwargs)
    return []


def _nervous_look(n_repeats=None):
    """
    Look left/right with wide pupils, then re-centre into focus for a moment, then relaxed.
    n_repeats: number of left-right cycles (default random 2–3).
    """
    if n_repeats is None:
        n_repeats = random.randint(2, 3)
    n_repeats = max(1, min(5, int(n_repeats)))
    # Wide pupils while looking left and right
    segments = []
    for _ in range(n_repeats):
        segments.append((0.28, -1.0, 0.0, "wide"))   # look left
        segments.append((0.28, 1.0, 0.0, "wide"))   # look right
    # Re-centre with focused pupils, then relax
    segments.append((0.2, 0.0, 0.0, "focused"))     # move to centre, focused
    segments.append((0.07, 0.0, 0.0, "relaxed"))    # hold centre, back to normal
    return segments
