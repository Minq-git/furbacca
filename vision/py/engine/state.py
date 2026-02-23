from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Literal

import vision.py.messages as messages
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
from vision.py.assets import config
from vision.py.engine import animations, blink
from vision.py.engine.animations import AnimationSegment


@dataclass
class FrameIntent:
    kind: Literal["open", "spinner", "closed_overlay", "blink_overlay"]
    inside_out: bool = False
    outside_in: bool = False


class FurbaccaState:
    """
    Mutable eye state + timing. Owns command application and per-frame tick logic.
    Rendering is still handled by engine.render, but the decision of which frames to show lives here.
    """

    def __init__(self) -> None:
        # --- Easing table ---
        ease_index_max = int(config.EASE_TABLE_SIZE) - 1
        self._ease_index_max = ease_index_max
        self._ease_table = tuple(
            int(config.EASE_TABLE_SIZE * (3.0 * (i / ease_index_max) ** 2 - 2.0 * (i / ease_index_max) ** 3))
            for i in range(config.EASE_TABLE_SIZE)
        )

        # --- Look / idle motion ---
        self.pupil_x: float = 0.0
        self.pupil_y: float = 0.0
        self.target_x: float = 0.0
        self.target_y: float = 0.0
        self.eye_in_motion = False
        self.eye_old_x: float = 0.0
        self.eye_old_y: float = 0.0
        self.eye_new_x: float = 0.0
        self.eye_new_y: float = 0.0
        self.eye_move_start: float = 0.0
        self.eye_move_duration: float = 0.0
        self.eye_hold_until: float = 0.0
        self.last_look_time: float = 0.0

        # Config constants (force concrete numeric types so they don't taint state math as Unknown/Any)
        self._look_clamp_min: float = float(config.LOOK_CLAMP_MIN)
        self._look_clamp_max: float = float(config.LOOK_CLAMP_MAX)
        self._focus_hold_s: float = float(config.FOCUS_HOLD_S)
        self._shiver_debounce_s: float = float(config.SHIVER_DEBOUNCE_S)
        self._idle_look_timeout_s: float = float(config.IDLE_LOOK_TIMEOUT_S)
        self._pupil_ease_factor: float = float(config.PUPIL_EASE_FACTOR)
        self._hold_duration_max_s: float = float(config.HOLD_DURATION_MAX_S)
        self._idle_wander_min: float = float(config.IDLE_WANDER_MIN)
        self._idle_wander_max: float = float(config.IDLE_WANDER_MAX)
        self._move_duration_min_s: float = float(config.MOVE_DURATION_MIN_S)
        self._move_duration_max_s: float = float(config.MOVE_DURATION_MAX_S)
        self._pupil_transition_anim_s: float = float(config.PUPIL_TRANSITION_ANIM_S)
        self._pupil_transition_s: float = float(config.PUPIL_TRANSITION_S)

        # --- Lids / warmup ---
        self.lids_held_closed = True
        self.has_opened_once = False
        self.warmup_step = 0
        self._blit_open_bottom_to_top = False
        self._sleep_close_hold = False

        # --- Blink ---
        self.animated_blink = blink.AnimatedBlink()
        self.next_auto_blink = time.monotonic() + blink.next_auto_blink_delay()

        # --- Animation segments ---
        self.animation_segments: list[AnimationSegment] = []
        self.animation_start_time = 0.0
        self.animation_index = 0
        self.segment_start_x: float = 0.0
        self.segment_start_y: float = 0.0
        self.last_blink_triggered_segment_index: int = int(config.SEGMENT_INDEX_NONE)

        # --- Pupil radius ---
        relaxed, focused, wide = config.eye_type_pupil_radii(config.get_eye_type())
        relaxed_i, focused_i, wide_i = int(relaxed), int(focused), int(wide)
        self._relaxed = relaxed_i
        self._focused = focused_i
        self._wide = wide_i
        self.focus_until = 0.0
        self.wide_until = 0.0  # (currently unused by sender, but retained)
        self.pupil_radius_current = float(relaxed_i)
        self.pupil_radius_target = relaxed_i
        self._radius_transition_start = 0.0
        self._radius_transition_from = float(relaxed_i)
        self._radius_transition_to = float(relaxed_i)

        # --- Impulse debounce ---
        self._last_impulse_at = 0.0

        # --- Eye base rebuild signal (eye type changes) ---
        self.needs_eye_base_rebuild = False

        # --- Restart signal (hardware) ---
        self.restart_requested = False

        # --- Output of tick() (consumed by RenderEngine) ---
        self.frame_intent: FrameIntent = FrameIntent(kind="spinner")

    # ----- Commands -----

    def update(self, cmd: EyesCommand, now: float) -> None:
        self.apply(cmd, now)

    def apply(self, cmd: EyesCommand, now: float) -> None:
        if isinstance(cmd, RestartBothCommand):
            self.restart_requested = True
            return

        if isinstance(cmd, EyesOpenCommand):
            self._on_eyes_open(now)
            return

        if isinstance(cmd, EyesCloseCommand):
            self.lids_held_closed = True
            return

        if isinstance(cmd, SleepCloseCommand):
            if not self.lids_held_closed and not self.animated_blink.is_closed:
                default_duration = getattr(config, "SLEEP_CLOSE_DURATION_S", 1.0)
                min_duration = getattr(config, "SLEEP_CLOSE_MIN_S", 0.2)
                duration_s = max(min_duration, float(cmd.duration_s or default_duration))
                self._sleep_close_hold = True
                self.animated_blink.trigger_sleep(now, duration_s)
            return

        if isinstance(cmd, WarmupCommand):
            self.warmup_step = max(0, min(config.EYE_WARMUP_STEPS - 1, int(cmd.step)))
            return

        if isinstance(cmd, BlinkCommand):
            if not self.lids_held_closed and not self.animation_segments and self.animated_blink.can_trigger(now):
                print("  👁  UDP: blink")
                self.animated_blink.trigger(now)
            return

        if isinstance(cmd, LookCommand):
            self.target_x = max(self._look_clamp_min, min(self._look_clamp_max, float(cmd.x)))
            self.target_y = max(self._look_clamp_min, min(self._look_clamp_max, float(cmd.y)))
            self.last_look_time = now
            self.focus_until = now + self._focus_hold_s
            return

        if isinstance(cmd, SetEyeShapeCommand):
            shape = (cmd.shape or "round").strip().lower()
            config.set_eye_shape(shape)
            print(messages.get("eyes", "eye_shape", shape=config.get_eye_shape()))
            return

        if isinstance(cmd, SetEyeTypeCommand):
            eye_type = str(cmd.type or cmd.eye_type or "default").strip().lower()
            config.set_eye_type(eye_type)
            self._refresh_pupil_radii()
            self.needs_eye_base_rebuild = True
            print(messages.get("eyes", "eye_type", type=config.get_eye_type()))
            return

        if isinstance(cmd, CycleEyeTypeCommand):
            _ = config.cycle_eye_type()
            self._refresh_pupil_radii()
            self.needs_eye_base_rebuild = True
            print(messages.get("eyes", "eye_type", type=config.get_eye_type()))
            return

        if isinstance(cmd, AnimationCommand):
            anim_name = (cmd.name or "").strip().lower()
            if anim_name:
                self._start_animation(anim_name, now=now, replace=bool(cmd.replace))
            return

        if isinstance(cmd, ImpulseCommand):
            if (now - self._last_impulse_at) >= self._shiver_debounce_s:
                self._last_impulse_at = now
                self._start_animation("shiver", now=now, replace=True)
            return

    def on_restart_succeeded(self, now: float) -> None:
        self.restart_requested = False
        self._on_eyes_open(now)

    def on_restart_failed(self) -> None:
        self.restart_requested = False

    def _on_eyes_open(self, now: float) -> None:
        self.lids_held_closed = False
        self.has_opened_once = True
        self._start_animation("double_blink", now=now, replace=True)
        # On open we want the next visible frame to "wipe" in.
        self._blit_open_bottom_to_top = True
        # Reset blink timers so we don't immediately auto-blink.
        self.next_auto_blink = now + blink.next_auto_blink_delay()

    def _refresh_pupil_radii(self) -> None:
        relaxed, focused, wide = config.eye_type_pupil_radii(config.get_eye_type())
        relaxed_i, focused_i, wide_i = int(relaxed), int(focused), int(wide)
        self._relaxed, self._focused, self._wide = relaxed_i, focused_i, wide_i
        self.pupil_radius_current = float(relaxed_i)
        self.pupil_radius_target = relaxed_i
        self._radius_transition_from = float(relaxed_i)
        self._radius_transition_to = float(relaxed_i)

    def _start_animation(self, name: str, now: float, replace: bool = False) -> None:
        if self.animation_segments and not replace:
            return
        segments = animations.get_animation(name)
        if not segments:
            return
        self.animation_segments = segments
        self.last_blink_triggered_segment_index = int(config.SEGMENT_INDEX_NONE)
        self.animation_start_time = now
        self.animation_index = 0
        self.segment_start_x, self.segment_start_y = self.pupil_x, self.pupil_y
        print(messages.get("eyes", "animation", name=name))

    # ----- Tick / render planning -----

    def tick(self, now: float) -> None:
        # --- Auto-blink trigger ---
        if (
            not self.lids_held_closed
            and not self.animation_segments
            and not self.animated_blink.is_closed
            and now >= self.next_auto_blink
        ):
            self.animated_blink.trigger(now)

        # --- Blink advance ---
        just_opened, next_delay = self.animated_blink.advance(now)
        if just_opened:
            if self._sleep_close_hold:
                self._sleep_close_hold = False
                self.lids_held_closed = True
            else:
                self._blit_open_bottom_to_top = True
                self.next_auto_blink = now + (next_delay if next_delay is not None else blink.next_auto_blink_delay())

        # --- Animation segments ---
        if self.animation_segments:
            seg: AnimationSegment = self.animation_segments[self.animation_index]
            if (
                getattr(seg, "trigger_blink", False)
                and self.animation_index != self.last_blink_triggered_segment_index
                and self.animated_blink.can_trigger(now)
            ):
                self.animated_blink.trigger(now)
                self.last_blink_triggered_segment_index = self.animation_index

            elapsed = now - self.animation_start_time
            progress = min(1.0, max(0.0, elapsed / seg.duration)) if seg.duration > 0 else 1.0
            idx = min(self._ease_index_max, int(progress * self._ease_index_max))
            e = self._ease_table[idx] / self._ease_index_max
            self.pupil_x = self.segment_start_x + (seg.x - self.segment_start_x) * e
            self.pupil_y = self.segment_start_y + (seg.y - self.segment_start_y) * e

            if elapsed >= seg.duration:
                self.animation_index += 1
                self.animation_start_time = now
                if self.animation_index >= len(self.animation_segments):
                    self.animation_segments = []
                    self.last_blink_triggered_segment_index = int(config.SEGMENT_INDEX_NONE)
                else:
                    self.segment_start_x, self.segment_start_y = self.pupil_x, self.pupil_y

        # --- Physics: idle looking ---
        if not self.animation_segments:
            if (now - self.last_look_time) <= self._idle_look_timeout_s:
                self.pupil_x += (self.target_x - self.pupil_x) * self._pupil_ease_factor
                self.pupil_y += (self.target_y - self.pupil_y) * self._pupil_ease_factor
            else:
                if self.eye_in_motion:
                    elapsed = now - self.eye_move_start
                    t = min(1.0, elapsed / self.eye_move_duration) if self.eye_move_duration > 0 else 1.0
                    e = (
                        self._ease_table[min(self._ease_index_max, int(t * self._ease_index_max))]
                        / self._ease_index_max
                    )
                    self.pupil_x = self.eye_old_x + (self.eye_new_x - self.eye_old_x) * e
                    self.pupil_y = self.eye_old_y + (self.eye_new_y - self.eye_old_y) * e
                    if elapsed >= self.eye_move_duration:
                        self.eye_in_motion = False
                        self.eye_hold_until = now + random.uniform(0.0, self._hold_duration_max_s)
                elif now >= self.eye_hold_until:
                    self.eye_old_x, self.eye_old_y = self.pupil_x, self.pupil_y
                    self.eye_new_x, self.eye_new_y = (
                        random.uniform(self._idle_wander_min, self._idle_wander_max),
                        random.uniform(self._idle_wander_min, self._idle_wander_max),
                    )
                    self.eye_move_start, self.eye_move_duration = (
                        now,
                        random.uniform(self._move_duration_min_s, self._move_duration_max_s),
                    )
                    self.eye_in_motion = True

        # --- Pupil radius ---
        relaxed, focused, wide = config.eye_type_pupil_radii(config.get_eye_type())
        relaxed_i, focused_i, wide_i = int(relaxed), int(focused), int(wide)
        self._relaxed, self._focused, self._wide = relaxed_i, focused_i, wide_i

        if self.animation_segments and self.animation_index < len(self.animation_segments):
            current_seg: AnimationSegment = self.animation_segments[self.animation_index]
            if current_seg.pupil_mode == "wide":
                self.pupil_radius_target = wide_i
            elif current_seg.pupil_mode == "focused":
                self.pupil_radius_target = focused_i
            else:
                self.pupil_radius_target = relaxed_i
            self.pupil_radius_current = float(self.pupil_radius_target)
            self._radius_transition_from = float(self.pupil_radius_target)
            self._radius_transition_to = float(self.pupil_radius_target)
        elif now < self.focus_until:
            self.pupil_radius_target = focused_i
        elif now < self.wide_until:
            self.pupil_radius_target = wide_i
        else:
            self.pupil_radius_target = relaxed_i

        if self.pupil_radius_target != self._radius_transition_to:
            self._radius_transition_from = self.pupil_radius_current
            self._radius_transition_to = self.pupil_radius_target
            self._radius_transition_start = now

        transition_s = self._pupil_transition_anim_s if self.animation_segments else self._pupil_transition_s
        elapsed_r = now - self._radius_transition_start
        if elapsed_r >= transition_s or self._radius_transition_from == self._radius_transition_to:
            self.pupil_radius_current = float(self._radius_transition_to)
        else:
            progress = min(1.0, elapsed_r / transition_s)
            idx = min(self._ease_index_max, int(progress * self._ease_index_max))
            e_r = self._ease_table[idx] / self._ease_index_max
            self.pupil_radius_current = self._radius_transition_from + (
                (self._radius_transition_to - self._radius_transition_from) * e_r
            )

        # --- Decide what to show (RenderEngine does the drawing) ---
        if self._blit_open_bottom_to_top:
            self._blit_open_bottom_to_top = False
            self.frame_intent = FrameIntent(kind="open", inside_out=True)
            return

        if self.lids_held_closed:
            if not self.has_opened_once:
                self.frame_intent = FrameIntent(kind="spinner")
                return
            self.frame_intent = FrameIntent(kind="closed_overlay")
            return

        if self.animated_blink.is_closed:
            self.frame_intent = FrameIntent(kind="blink_overlay", outside_in=True)
            return

        self.frame_intent = FrameIntent(kind="open")
        return
