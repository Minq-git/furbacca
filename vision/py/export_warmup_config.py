"""Print warmup config as JSON so nervous_system (Node) can read config.py values. Run from repo root: python3 vision/py/export_warmup_config.py"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

print(json.dumps({
    "EYE_WARMUP_STEPS": config.EYE_WARMUP_STEPS,
    "WARMUP_MS": config.WARMUP_MS,
    "WARMUP_BEIGE": list(config.WARMUP_BEIGE),
    "WARMUP_GREEN": list(config.WARMUP_GREEN),
    "STATUS_FAIL_RED": list(config.STATUS_FAIL_RED),
}))
