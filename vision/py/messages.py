"""
Central user-facing messages. Loaded from messages.json at repo root.
Use messages.msg["eyes"]["opening_animated"] or messages.get("eyes", "opening_animated", fps=30).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_MESSAGES_PATH = _REPO_ROOT / "messages.json"

with open(_MESSAGES_PATH, encoding="utf-8") as f:
    msg = cast(dict[str, dict[str, str]], json.load(f))


def get(section: str, key: str, **params: str | int) -> str:
    """Get a message string and substitute {key} with params."""
    template = msg[section][key]
    for k, v in params.items():
        template = template.replace("{" + k + "}", str(v))
    return template
