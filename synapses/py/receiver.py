from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from typing import Any, cast

from synapses.py.vision_messages import (
    AnimationCommand,
    BlinkCommand,
    CycleEyeTypeCommand,
    EyesCloseCommand,
    EyesCommand,
    EyesOpenCommand,
    ImpulseCommand,
    LookCommand,
    RestartBothCommand,
    SetEyeShapeCommand,
    SetEyeTypeCommand,
    SleepCloseCommand,
    WarmupCommand,
)


def _json_loads_object(s: str) -> object:
    return cast(object, json.loads(s))


@dataclass
class SynapseReceiver:
    """
    Non-blocking UDP receiver for Nervous System → Eyes commands (UDP 5005).
    Converts raw JSON dicts into typed command dataclasses.
    """

    port: int = 5005
    bind: str = "127.0.0.1"
    recv_size: int = 4096

    def __post_init__(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.bind, self.port))
        sock.setblocking(False)
        self._sock = sock

    def poll(self) -> EyesCommand | None:
        try:
            recv = self._sock.recvfrom(self.recv_size)
        except BlockingIOError:
            return None

        data = recv[0]
        _addr: tuple[str, int] = cast(tuple[str, int], recv[1])
        try:
            raw = _json_loads_object(data.decode())
        except json.JSONDecodeError:
            return None

        if not isinstance(raw, dict):
            return None

        msg = cast(dict[str, object], raw)
        action = str(msg.get("action", "look"))
        msg_any = cast(dict[str, Any], msg)
        if action == "look":
            return LookCommand.from_dict(msg_any)
        if action == "animation":
            return AnimationCommand.from_dict(msg_any)
        if action == "eyes_open":
            return EyesOpenCommand.from_dict(msg_any)
        if action == "eyes_close":
            return EyesCloseCommand.from_dict(msg_any)
        if action == "sleep_close":
            return SleepCloseCommand.from_dict(msg_any)
        if action == "warmup":
            return WarmupCommand.from_dict(msg_any)
        if action == "set_eye_shape":
            return SetEyeShapeCommand.from_dict(msg_any)
        if action == "set_eye_type":
            return SetEyeTypeCommand.from_dict(msg_any)
        if action == "cycle_eye_type":
            return CycleEyeTypeCommand.from_dict(msg_any)
        if action == "blink":
            return BlinkCommand.from_dict(msg_any)
        if action == "impulse":
            return ImpulseCommand.from_dict(msg_any)
        if action in ("restart_both", "restart", "refresh"):
            return RestartBothCommand.from_dict(msg_any)

        return None
