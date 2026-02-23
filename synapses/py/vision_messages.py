"""
UDP message contracts shared with synapses/ts. Keep in sync when adding fields.
"""

import json
from dataclasses import dataclass
from typing import Any, Literal, cast

# --- UDP 5005: Nervous System → Eyes ---


@dataclass
class LookCommand:
    action: Literal["look"] = "look"
    x: float = 0.0
    y: float = 0.0
    pupil_mode: str = "normal"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LookCommand":
        return cls(
            action="look",
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
class AnimationCommand:
    action: Literal["animation"] = "animation"
    name: str = ""
    replace: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnimationCommand":
        return cls(
            action="animation",
            name=str(cast(str, data.get("name", ""))),
            replace=bool(data.get("replace") is True),
        )


@dataclass
class EyesOpenCommand:
    action: Literal["eyes_open"] = "eyes_open"

    @classmethod
    def from_dict(cls, _data: dict[str, Any]) -> "EyesOpenCommand":
        return cls()


@dataclass
class EyesCloseCommand:
    action: Literal["eyes_close"] = "eyes_close"

    @classmethod
    def from_dict(cls, _data: dict[str, Any]) -> "EyesCloseCommand":
        return cls()


@dataclass
class SleepCloseCommand:
    action: Literal["sleep_close"] = "sleep_close"
    duration_s: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SleepCloseCommand":
        duration_raw = data.get("duration_s")
        duration_s = float(cast(int | float, duration_raw)) if duration_raw is not None else None
        return cls(duration_s=duration_s)


@dataclass
class WarmupCommand:
    action: Literal["warmup"] = "warmup"
    step: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WarmupCommand":
        return cls(step=int(cast(int | str, data.get("step", 0))))


@dataclass
class SetEyeShapeCommand:
    action: Literal["set_eye_shape"] = "set_eye_shape"
    shape: str = "round"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SetEyeShapeCommand":
        return cls(shape=str(cast(str, data.get("shape", "round"))))


@dataclass
class SetEyeTypeCommand:
    action: Literal["set_eye_type"] = "set_eye_type"
    type: str | None = None
    eye_type: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SetEyeTypeCommand":
        return cls(
            type=cast(str | None, data.get("type")),
            eye_type=cast(str | None, data.get("eye_type")),
        )


@dataclass
class CycleEyeTypeCommand:
    action: Literal["cycle_eye_type"] = "cycle_eye_type"

    @classmethod
    def from_dict(cls, _data: dict[str, Any]) -> "CycleEyeTypeCommand":
        return cls()


@dataclass
class BlinkCommand:
    action: Literal["blink"] = "blink"

    @classmethod
    def from_dict(cls, _data: dict[str, Any]) -> "BlinkCommand":
        return cls()


@dataclass
class ImpulseCommand:
    action: Literal["impulse"] = "impulse"

    @classmethod
    def from_dict(cls, _data: dict[str, Any]) -> "ImpulseCommand":
        return cls()


@dataclass
class RestartBothCommand:
    action: Literal["restart_both"] = "restart_both"

    @classmethod
    def from_dict(cls, _data: dict[str, Any]) -> "RestartBothCommand":
        return cls()


EyesCommand = (
    LookCommand
    | AnimationCommand
    | EyesOpenCommand
    | EyesCloseCommand
    | SleepCloseCommand
    | WarmupCommand
    | SetEyeShapeCommand
    | SetEyeTypeCommand
    | CycleEyeTypeCommand
    | BlinkCommand
    | ImpulseCommand
    | RestartBothCommand
)


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
