"""
Blink state and timing for animated and static eye loops.
Constants live in config; this module uses them for state machine logic.
"""
import random

try:
    import config
except ImportError:
    config = None

def _blink_debounce_s():
    return config.BLINK_DEBOUNCE_S if config else 0.2

def random_closing_duration():
    """Random closed duration for animated blink (seconds)."""
    if config:
        return random.uniform(config.BLINK_CLOSING_S_MIN, config.BLINK_CLOSING_S_MAX)
    return random.uniform(0.04, 0.07)


def next_auto_blink_delay():
    """Seconds until next auto-blink (animated loop)."""
    if config:
        return random.uniform(config.BLINK_AUTO_DELAY_MIN_S, config.BLINK_AUTO_DELAY_MAX_S)
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
        return (now - self.last_blink_end) >= _blink_debounce_s()

    def trigger(self, now):
        self.phase = "closing"
        self.start_time = now
        self.last_blink_end = now
        self.closing_duration_s = random_closing_duration()

    def trigger_sleep(self, now, duration_s=None):
        """Trigger a slow close for sleep (same animation, longer duration); caller holds closed when advance returns just_opened."""
        if duration_s is None:
            duration_s = config.SLEEP_CLOSE_DURATION_S if config else 1.0
        min_s = config.SLEEP_CLOSE_MIN_S if config else 0.2
        self.phase = "closing"
        self.start_time = now
        self.last_blink_end = now
        self.closing_duration_s = max(min_s, float(duration_s))

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
        base = config.BLINK_AFTER_CLOSE_BASE_S if config else 3.0
        rnd = config.BLINK_AFTER_CLOSE_RANDOM_S if config else 4.0
        delay = (total_s * base) + random.uniform(0.0, rnd)
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
        return (now - self.last_blink_end) >= _blink_debounce_s()

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
