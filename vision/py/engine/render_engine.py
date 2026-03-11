from __future__ import annotations

import time
from dataclasses import dataclass

from vision.py.assets import config
from vision.py.engine import render
from vision.py.engine.state import FurbaccaState


@dataclass
class FramePlan:
    left: object | None
    right: object | None
    inside_out: bool = False
    outside_in: bool = False


class RenderEngine:
    def __init__(self, fps: float) -> None:
        self.frame_dt = 1.0 / max(1.0, float(fps))
        self._cached_eye_base_240: object | None = None

    def generate_frame(self, state: FurbaccaState, now: float) -> FramePlan:
        if state.needs_eye_base_rebuild:
            self._cached_eye_base_240 = render.build_eye_base_sclera_iris()
            state.needs_eye_base_rebuild = False

        intent = state.frame_intent
        if intent.kind == "spinner":
            color_phase = state.warmup_step / max(1, config.EYE_WARMUP_STEPS - 1)
            spin_l = render.render_spinner(-now * 3.2, mirror=False, color_phase=color_phase)
            spin_r = render.render_spinner(-now * 3.2, mirror=True, color_phase=color_phase)
            return FramePlan(left=spin_l, right=spin_r)

        if intent.kind == "closed_overlay":
            overlay_l = render.render_blink_overlay(mirror=False)
            overlay_r = render.render_blink_overlay(mirror=True)
            return FramePlan(left=overlay_l, right=overlay_r)

        if intent.kind == "blink_overlay":
            overlay_l = render.render_blink_overlay(mirror=False)
            overlay_r = render.render_blink_overlay(mirror=True)
            return FramePlan(left=overlay_l, right=overlay_r, outside_in=intent.outside_in)

        # intent.kind == "open" — per-eye chassis alignment (displays skewed/closer in Furby chassis)
        lx = state.pupil_x + config.PUPIL_OFFSET_LEFT_X
        ly = state.pupil_y + config.PUPIL_OFFSET_LEFT_Y
        rx = state.pupil_x + config.PUPIL_OFFSET_RIGHT_X
        ry = state.pupil_y + config.PUPIL_OFFSET_RIGHT_Y
        eye_frame_left = render.render_animated_frame(
            self._cached_eye_base_240,
            lx,
            ly,
            "open",
            pupil_radius=state.pupil_radius_current,
        )
        eye_frame_right = render.render_animated_frame(
            self._cached_eye_base_240,
            rx,
            ry,
            "open",
            pupil_radius=state.pupil_radius_current,
        )
        return FramePlan(
            left=eye_frame_left,
            right=eye_frame_right,
            inside_out=intent.inside_out,
            outside_in=intent.outside_in,
        )

    def sleep_until_next_frame(self, frame_started_at: float) -> None:
        time.sleep(max(0.0, self.frame_dt - (time.monotonic() - frame_started_at)))
