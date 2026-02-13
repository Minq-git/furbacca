"""
Preset eye animations for Furbacca.
Each animation is a list of AnimationSegment objects.
"""
import random
from typing import List, Optional, NamedTuple

# Descriptive labels for pupil modes
PUPIL_RELAXED = "relaxed"
PUPIL_FOCUSED = "focused"
PUPIL_WIDE = "wide"

class AnimationSegment(NamedTuple):
    duration: float
    x: float
    y: float
    pupil_mode: str = PUPIL_RELAXED

def get_animation(name: str, **kwargs) -> List[AnimationSegment]:
    """
    Registry for named animations.
    """
    name = (name or "").strip().lower()
    
    animations_map = {
        "nervous_look": _nervous_look,
        "shiver": _shiver,
    }
    
    func = animations_map.get(name)
    return func(**kwargs) if func else []

def _shiver() -> List[AnimationSegment]:
    """
    High-frequency vibration with rapid decay.
    """
    return [
        # Impact
        AnimationSegment(0.001,  0.40,  0.08, PUPIL_FOCUSED), 
        AnimationSegment(0.001, -0.35, -0.06, PUPIL_FOCUSED),
        # Decay
        AnimationSegment(0.001,  0.25,  0.04, PUPIL_RELAXED),
        AnimationSegment(0.001, -0.18, -0.03, PUPIL_RELAXED),
        # Settle
        AnimationSegment(0.002,  0.08,  0.02, PUPIL_RELAXED),
        AnimationSegment(0.002, -0.04, -0.01, PUPIL_RELAXED),
        # Rest
        AnimationSegment(0.050,  0.00,  0.00, PUPIL_RELAXED),
    ]

def _nervous_look(n_repeats: Optional[int] = None) -> List[AnimationSegment]:
    """
    Rapid side-to-side scanning with focused pupils.
    """
    if n_repeats is None:
        n_repeats = random.randint(2, 3)
    n_repeats = max(1, min(5, int(n_repeats)))

    segments = []
    for _ in range(n_repeats):
        segments.append(AnimationSegment(0.28, -1.0, 0.0, PUPIL_FOCUSED)) # Left
        segments.append(AnimationSegment(0.28,  1.0, 0.0, PUPIL_FOCUSED)) # Right
        
    segments.append(AnimationSegment(0.90, 0.0, 0.0, PUPIL_RELAXED)) # Re-center
    return segments