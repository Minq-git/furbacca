"""Print warmup config as JSON so nervous_system (Node) can read config.py values. Run from repo root: python3 vision/py/export_warmup_config.py"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assets import config

print(
    json.dumps(
        {
            "EYE_WARMUP_STEPS": config.EYE_WARMUP_STEPS,
            "WARMUP_MS": config.WARMUP_MS,
            "WARMUP_BEIGE": list(config.WARMUP_BEIGE),
            "WARMUP_GREEN": list(config.WARMUP_GREEN),
            "STATUS_FAIL_RED": list(config.STATUS_FAIL_RED),
            "OPEN_THEN_LOOK_MS": config.OPEN_THEN_LOOK_MS,
            "MOTION_SLEEP_MS": config.MOTION_SLEEP_MS,
            "MOTION_RESPONSE_COOLDOWN_MS": config.MOTION_RESPONSE_COOLDOWN_MS,
            "MOTION_CLEAR_DEBOUNCE_MS": config.MOTION_CLEAR_DEBOUNCE_MS,
            "SLEEP_CLOSE_DURATION_S": config.SLEEP_CLOSE_DURATION_S,
        }
    )
)
