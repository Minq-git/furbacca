"""
Blink state and timing for animated and static eye loops.
Constants and small state machines so eyes.py stays focused on display/blit.
"""
import random

BLINK_DEBOUNCE_S = 0.2
CLOSING_S_MIN = 0.04
CLOSING_S_MAX = 0.07


def random_closing_duration():
    """Random closed duration for animated blink (seconds)."""
    return random.uniform(CLOSING_S_MIN, CLOSING_S_MAX)


def next_auto_blink_delay():
    """Seconds until next auto-blink (animated loop)."""
    return random.uniform(2.0, 5.0)


class AnimatedBlink:
    """Blink state for the animated eye loop (timed close then open)."""
    __slots__ = ("phase", "start_time", "closing_duration_s", "last_blink_end")

    def __init__(self):
        self.phase = None  # None | "closing"
        self.start_time = 0.0
        self.closing_duration_s = 0.05
        self.last_blink_end = 0.0

    def can_trigger(self, now):
        return (now - self.last_blink_end) >= BLINK_DEBOUNCE_S

    def trigger(self, now):
        self.phase = "closing"
        self.start_time = now
        self.last_blink_end = now
        self.closing_duration_s = random_closing_duration()

    def advance(self, now):
        """
        Advance state. Returns (just_opened, next_auto_delay).
        just_opened: True when we transition from closed to open (caller may run cycle_eye_type etc.).
        next_auto_delay: seconds until next auto-blink, or None if not just opened.
        """
        if self.phase != "closing":
            return False, None
        if (now - self.start_time) < self.closing_duration_s:
            return False, None
        total_s = now - self.start_time
        self.phase = None
        delay = (total_s * 3.0) + random.uniform(0.0, 4.0)
        return True, delay

    @property
    def is_closed(self):
        return self.phase is not None


class StaticBlink:
    """Blink state for the static eye loop (one frame closed, one frame opening)."""
    __slots__ = ("phase", "last_blink_end")

    def __init__(self):
        self.phase = None  # None | "closing" | "opening"
        self.last_blink_end = 0.0

    def can_trigger(self, now):
        return (now - self.last_blink_end) >= BLINK_DEBOUNCE_S

    def trigger(self, now):
        self.phase = "closing"
        self.last_blink_end = now

    def advance(self):
        """
        Advance to next phase: closing -> opening -> None.
        Returns True when transitioning from opening to None (caller may run cycle_eye_type).
        """
        if self.phase == "closing":
            self.phase = "opening"
            return False
        if self.phase == "opening":
            self.phase = None
            return True
        return False

    @property
    def is_closing(self):
        return self.phase == "closing"

    @property
    def is_opening(self):
        return self.phase == "opening"
