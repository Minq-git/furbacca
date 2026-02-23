"""
UDP message contracts shared with synapses/ts. Keep in sync when adding fields.
"""

import json
from dataclasses import dataclass
from typing import Any, cast

# --- UDP 5005: Nervous System → Eyes ---


@dataclass
class LookCommand:
    action: str = "look"
    x: float = 0.0
    y: float = 0.0
    pupil_mode: str = "normal"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LookCommand":
        return cls(
            action=str(cast(str, data.get("action", "look"))),
            x=float(cast(int | float, data.get("x", 0))),
            y=float(cast(int | float, data.get("y", 0))),
            pupil_mode=str(cast(str, data.get("pupil_mode", "normal"))),
        )

    def to_json(self) -> str:
        out: dict[str, Any] = {"action": self.action, "x": self.x, "y": self.y}
        if self.pupil_mode != "normal":
            out["pupil_mode"] = self.pupil_mode
        return json.dumps(out)


@dataclass
class EyeTrackingEvent:
    """UDP 5006: Camera / eye-track → Nervous System."""

    event: str
    label: str | None = None
    confidence: float | None = None
    x: float | None = None
    y: float | None = None

    def to_json(self) -> str:
        d: dict[str, Any] = {"event": self.event}
        if self.label is not None:
            d["label"] = self.label
        if self.confidence is not None:
            d["confidence"] = self.confidence
        if self.x is not None:
            d["x"] = self.x
        if self.y is not None:
            d["y"] = self.y
        return json.dumps(d)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EyeTrackingEvent":
        return cls(
            event=str(cast(str, data.get("event", ""))),
            label=cast(str | None, data.get("label")),
            confidence=cast(float | None, data.get("confidence")),
            x=cast(float | None, data.get("x")),
            y=cast(float | None, data.get("y")),
        )
