"""
Furbacca vision: dual GC9A01 eyes using russhughes/gc9a01py (CPython compat layer).
Restored version with original state logic + NumPy performance optimizations.
"""
import json
import os
import signal
import socket
import sys
import threading
import time
import random

_shutdown_requested = False

def _handle_shutdown(signum, frame):
    global _shutdown_requested
    _shutdown_requested = True

_vision_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _vision_dir)

try:
    import numpy as np
except ImportError:
    np = None

import config
import assets
import blit
import render
import shapes
import test_patterns
import animations
import blink
from display import init_displays

# Re-export for callers
get_eye_type = config.get_eye_type
set_eye_type = config.set_eye_type

# Display handles
left_eye, right_eye = None, None
try:
    left_eye, right_eye = init_displays(swap_left_right=config.SWAP_LEFT_RIGHT_SPI)
except Exception as e:
    print(f"⚠ Display init failed: {e}")

# UDP bridge
UDP_BIND = os.environ.get("UDP_BIND", "127.0.0.1").strip() or "127.0.0.1"
UDP_PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((UDP_BIND, UDP_PORT))
sock.setblocking(False)
print(f"  UDP {UDP_BIND}:{UDP_PORT} (remote fe + local nervous system)")

def _apply_eye_shape_left(frame):
    if frame is None: return frame
    # frame is a PIL Image; convert to array for NumPy masking
    arr = np.array(frame, dtype=np.uint8)
    masked_arr = shapes.apply_shape_mask_numpy(arr, config.get_eye_shape(), mirror=False)
    # Copy so the PIL Image owns its data (avoids async blit seeing reused buffer → one eye blackout)
    from PIL import Image
    return Image.fromarray(masked_arr.copy())

def _apply_eye_shape_right(frame):
    if frame is None: return frame
    arr = np.array(frame, dtype=np.uint8)
    masked_arr = shapes.apply_shape_mask_numpy(arr, config.get_eye_shape(), mirror=True)
    from PIL import Image
    return Image.fromarray(masked_arr.copy())

def run_eyes():
    if left_eye is None and right_eye is None:
        return

    print("👀 Furbacca Vision Online (Optimized).")
    # Pre-load other eye types in background; current type loads on first frame (faster startup)
    _current_type = config.get_eye_type()
    _preload_thread = threading.Thread(
        target=lambda: render.preload_all_types(skip_type=_current_type),
        daemon=True,
    )
    _preload_thread.start()

    use_animated = (
        config.EYES_ANIMATED and not config.EYES_GRADIENT and not config.EYES_RAINBOW
        and assets.HAS_PIL
    )

    if use_animated:
        frame_dt = 1.0 / config.ANIM_FPS
        EASE_INDEX_MAX = config.EASE_TABLE_SIZE - 1

        print(f"👀 Animated eyes @ {config.ANIM_FPS} FPS. UDP enabled.")
        cached_eye_base_240 = None  # First frame fills cache for current type

        # Smoothstep easing: 3t² - 2t³ over [0,1]
        EASE_TABLE = tuple(
            int(config.EASE_TABLE_SIZE * (3.0 * (i / EASE_INDEX_MAX) ** 2 - 2.0 * (i / EASE_INDEX_MAX) ** 3))
            for i in range(config.EASE_TABLE_SIZE)
        )

        # --- State machine ---
        pupil_x, pupil_y = 0.0, 0.0
        target_x, target_y = 0.0, 0.0
        eye_in_motion = False
        eye_old_x, eye_old_y = 0.0, 0.0
        eye_new_x, eye_new_y = 0.0, 0.0
        eye_move_start = 0.0
        eye_move_duration = 0.0
        eye_hold_until = 0.0
        blit_open_bottom_to_top = False
        next_auto_blink = time.monotonic() + blink.next_auto_blink_delay()
        last_look_time = 0.0
        relaxed, focused, wide = config.eye_type_pupil_radii(config.get_eye_type())
        # Stay closed until nervous system sends eyes_open (graceful startup)
        lids_held_closed = True
        # One synchronous frame so both displays get a stable image before async (reduces right-eye crash at startup)
        first_frame = render.render_animated_frame(cached_eye_base_240, 0.0, 0.0, "open", pupil_radius=relaxed)
        if first_frame is not None:
            if lids_held_closed:
                overlay_l = render.render_blink_overlay(mirror=False)
                overlay_r = render.render_blink_overlay(mirror=True)
                if overlay_l and overlay_r:
                    blit.blit_pil_to_both(left_eye, right_eye, _apply_eye_shape_left(overlay_l), _apply_eye_shape_right(overlay_r), reverse_rows=False, outside_in=False, inside_out=False, partial_rows=None)
                else:
                    blit.blit_pil_to_both(left_eye, right_eye, _apply_eye_shape_left(first_frame), _apply_eye_shape_right(first_frame), reverse_rows=False, outside_in=False, inside_out=False, partial_rows=None)
            else:
                blit.blit_pil_to_both(left_eye, right_eye, _apply_eye_shape_left(first_frame), _apply_eye_shape_right(first_frame), reverse_rows=False, outside_in=False, inside_out=False, partial_rows=None)
        focus_until = 0.0
        wide_until = 0.0
        next_wide_at = 0.0
        pupil_radius_current = float(relaxed)
        pupil_radius_target = relaxed
        radius_transition_start = 0.0
        radius_transition_from = float(relaxed)
        radius_transition_to = float(relaxed)
        animated_blink = blink.AnimatedBlink()
        do_cycle_on_next_open = False
        animation_segments = []
        animation_start_time = 0.0
        animation_index = 0
        segment_start_x, segment_start_y = 0.0, 0.0
        segment_end_x, segment_end_y = 0.0, 0.0
        last_blink_triggered_segment_index = config.SEGMENT_INDEX_NONE
        last_impulse_at = 0.0

        signal.signal(signal.SIGINT, _handle_shutdown)
        signal.signal(signal.SIGTERM, _handle_shutdown)

        def _start_animation(name, replace=False):
            nonlocal animation_segments, animation_start_time, animation_index
            nonlocal segment_start_x, segment_start_y, segment_end_x, segment_end_y
            nonlocal last_blink_triggered_segment_index
            # If one is already running, only continue when replace=True (e.g. double head-tap restarts nervous_look)
            if animation_segments and not replace:
                return
            segments = animations.get_animation(name)
            if not segments:
                return
            animation_segments = segments
            last_blink_triggered_segment_index = config.SEGMENT_INDEX_NONE
            animation_start_time = time.monotonic()
            animation_index = 0
            segment_start_x, segment_start_y = pupil_x, pupil_y
            seg0 = animation_segments[0]
            segment_end_x, segment_end_y = seg0.x, seg0.y
            print(f"🎬 Animation: {name}")

        while True:
            if _shutdown_requested:
                break
            now = time.monotonic()
            # --- UDP Command Logic (Original) ---
            while True:
                try:
                    data, _ = sock.recvfrom(config.UDP_RECV_SIZE)
                    msg = json.loads(data.decode())
                    action = msg.get("action")
                    if action == "eyes_open":
                        lids_held_closed = False
                        _start_animation("double_blink", replace=True)  # wake-up double blink
                    elif action == "eyes_close":
                        lids_held_closed = True
                    elif action == "blink":
                        if not lids_held_closed and not animation_segments and animated_blink.can_trigger(now):
                            animated_blink.trigger(now)
                    elif action == "look":
                        tx, ty = msg.get("x"), msg.get("y")
                        if tx is not None: target_x = max(config.LOOK_CLAMP_MIN, min(config.LOOK_CLAMP_MAX, float(tx)))
                        if ty is not None: target_y = max(config.LOOK_CLAMP_MIN, min(config.LOOK_CLAMP_MAX, float(ty)))
                        last_look_time, focus_until = now, now + config.FOCUS_HOLD_S
                    elif action == "set_eye_shape":
                        shape = (msg.get("shape") or "round").strip().lower()
                        config.set_eye_shape(shape)
                    elif action == "set_eye_type":
                        eye_type = (msg.get("type") or msg.get("eye_type") or "default").strip().lower()
                        config.set_eye_type(eye_type)
                        cached_eye_base_240 = render.build_eye_base_sclera_iris()
                        relaxed, focused, wide = config.eye_type_pupil_radii(config.get_eye_type())
                        pupil_radius_current = float(relaxed)
                        print(f"👁 Eye type updated to: {config.get_eye_type()}")
                    elif action == "cycle_eye_type":
                        config.cycle_eye_type()
                        cached_eye_base_240 = render.build_eye_base_sclera_iris()
                        relaxed, focused, wide = config.eye_type_pupil_radii(config.get_eye_type())
                        pupil_radius_current = float(relaxed)
                        print(f"👁 Eye type cycled to: {config.get_eye_type()}")
                    elif action == "animation":
                        anim_name = (msg.get("name") or "").strip().lower()
                        replace = msg.get("replace") is True
                        if anim_name:
                            _start_animation(anim_name, replace=replace)
                    elif action == "impulse":
                        if (now - last_impulse_at) >= config.SHIVER_DEBOUNCE_S:
                            last_impulse_at = now
                            _start_animation("shiver")
                except (BlockingIOError, json.JSONDecodeError):
                    break

            # --- 1. Auto-blink Trigger ---
            # Trigger ONLY if the timer is up and we aren't already blinking (disabled while lids held closed at startup)
            if not lids_held_closed and not animation_segments and not animated_blink.is_closed and now >= next_auto_blink:
                animated_blink.trigger(now)
                # Important: DO NOT update next_auto_blink here. 
                # Let the advance() function decide the next time.

            # --- 2. Blink & State Advancement ---
            # This is where blink.py manages the duration and the NEXT delay
            just_opened, next_delay = animated_blink.advance(now)
            
            if just_opened:
                blit_open_bottom_to_top = True
                # Use the custom delay from blink.py (total_s * 3 + random)
                if next_delay is not None: 
                    next_auto_blink = now + next_delay
                else:
                    # Fallback only if advance failed
                    next_auto_blink = now + blink.next_auto_blink_delay()

            # --- Animation Segment Processing (Readable) ---
            if animation_segments:
                seg = animation_segments[animation_index]
                # Programmed blink: segment can request a blink even during animation (no blocker)
                if getattr(seg, "trigger_blink", False) and animation_index != last_blink_triggered_segment_index and animated_blink.can_trigger(now):
                    animated_blink.trigger(now)
                    last_blink_triggered_segment_index = animation_index
                elapsed = now - animation_start_time
                
                progress = min(1.0, max(0.0, elapsed / seg.duration)) if seg.duration > 0 else 1.0
                idx = min(EASE_INDEX_MAX, int(progress * EASE_INDEX_MAX))
                e = EASE_TABLE[idx] / EASE_INDEX_MAX

                pupil_x = segment_start_x + (seg.x - segment_start_x) * e
                pupil_y = segment_start_y + (seg.y - segment_start_y) * e
                
                if elapsed >= seg.duration:
                    animation_index += 1
                    animation_start_time = now
                    if animation_index >= len(animation_segments):
                        animation_segments = []
                        last_blink_triggered_segment_index = config.SEGMENT_INDEX_NONE
                    else:
                        segment_start_x, segment_start_y = pupil_x, pupil_y
                        next_seg = animation_segments[animation_index]

                        segment_end_x, segment_end_y = next_seg.x, next_seg.y

            # --- Physics: Idle Looking & Pupil Radius ---
            relaxed, focused, wide = config.eye_type_pupil_radii(config.get_eye_type())
            if not animation_segments:
                if (now - last_look_time) <= config.IDLE_LOOK_TIMEOUT_S:
                    pupil_x += (target_x - pupil_x) * config.PUPIL_EASE_FACTOR
                    pupil_y += (target_y - pupil_y) * config.PUPIL_EASE_FACTOR
                else:
                    if eye_in_motion:
                        elapsed = now - eye_move_start
                        t = min(1.0, elapsed / eye_move_duration) if eye_move_duration > 0 else 1.0
                        e = EASE_TABLE[min(EASE_INDEX_MAX, int(t * EASE_INDEX_MAX))] / EASE_INDEX_MAX
                        pupil_x = eye_old_x + (eye_new_x - eye_old_x) * e
                        pupil_y = eye_old_y + (eye_new_y - eye_old_y) * e
                        if elapsed >= eye_move_duration:
                            eye_in_motion = False
                            eye_hold_until = now + random.uniform(0.0, config.HOLD_DURATION_MAX_S)
                    elif now >= eye_hold_until:
                        eye_old_x, eye_old_y = pupil_x, pupil_y
                        eye_new_x, eye_new_y = random.uniform(config.IDLE_WANDER_MIN, config.IDLE_WANDER_MAX), random.uniform(config.IDLE_WANDER_MIN, config.IDLE_WANDER_MAX)
                        eye_move_start, eye_move_duration = now, random.uniform(config.MOVE_DURATION_MIN_S, config.MOVE_DURATION_MAX_S)
                        eye_in_motion = True

            # --- Pupil Radius: Logic with Animation Overrides ---
            relaxed, focused, wide = config.eye_type_pupil_radii(config.get_eye_type())
            
            if animation_segments and animation_index < len(animation_segments):
                seg = animation_segments[animation_index]
                # Check for pupil_mode override in the current segment
                if seg.pupil_mode == "wide":
                    pupil_radius_target = wide
                elif seg.pupil_mode == "focused":
                    pupil_radius_target = focused
                else:
                    pupil_radius_target = relaxed
                
                # Apply immediately for animations to feel snappy
                pupil_radius_current = float(pupil_radius_target)
                radius_transition_from = pupil_radius_target
                radius_transition_to = pupil_radius_target
            elif now < focus_until:
                pupil_radius_target = focused
            elif now < wide_until:
                pupil_radius_target = wide
            else:
                pupil_radius_target = relaxed

            # --- Transition Smoothing ---
            if pupil_radius_target != radius_transition_to:
                radius_transition_from = pupil_radius_current
                radius_transition_to = pupil_radius_target
                radius_transition_start = now
            
            # Use faster transitions during animations
            transition_s = config.PUPIL_TRANSITION_ANIM_S if animation_segments else config.PUPIL_TRANSITION_S
            
            elapsed_r = now - radius_transition_start
            if elapsed_r >= transition_s or radius_transition_from == radius_transition_to:
                pupil_radius_current = float(radius_transition_to)
            else:
                # Smoothly ease the radius change
                progress = min(1.0, elapsed_r / transition_s)
                idx = min(EASE_INDEX_MAX, int(progress * EASE_INDEX_MAX))
                e_r = EASE_TABLE[idx] / EASE_INDEX_MAX
                pupil_radius_current = radius_transition_from + (radius_transition_to - radius_transition_from) * e_r

            # --- Rendering & Async Blitting ---
            eye_frame = render.render_animated_frame(cached_eye_base_240, pupil_x, pupil_y, "open", pupil_radius=pupil_radius_current)
            
            if blit_open_bottom_to_top:
                blit.blit_pil_to_both_async(left_eye, right_eye, _apply_eye_shape_left(eye_frame), _apply_eye_shape_right(eye_frame), inside_out=True)
                blit_open_bottom_to_top = False
            elif animated_blink.is_closed or lids_held_closed:
                overlay_l = render.render_blink_overlay(mirror=False)
                overlay_r = render.render_blink_overlay(mirror=True)
                if overlay_l and overlay_r and np is not None:
                    # Composite overlay in NumPy (works whether eye_frame is PIL or ndarray)
                    def _composite_overlay(frame, overlay_pil):
                        ov = np.array(overlay_pil, dtype=np.uint8)
                        # Use full overlay (black eyelids + line) so closed eye shows black + line
                        from PIL import Image
                        return Image.fromarray(ov.copy())
                    comp_l = _composite_overlay(eye_frame, overlay_l)
                    comp_r = _composite_overlay(eye_frame, overlay_r)
                    blit.blit_pil_to_both_async(left_eye, right_eye, _apply_eye_shape_left(comp_l), _apply_eye_shape_right(comp_r), outside_in=True)
                elif overlay_l and overlay_r:
                    # PIL path when numpy unavailable (eye_frame assumed PIL from render)
                    from PIL import Image
                    pil_frame = Image.fromarray(eye_frame) if (np is not None and isinstance(eye_frame, np.ndarray)) else eye_frame
                    comp_l = pil_frame.copy()
                    comp_l.paste(overlay_l, (0, 0))
                    comp_r = pil_frame.copy()
                    comp_r.paste(overlay_r, (0, 0))
                    blit.blit_pil_to_both_async(left_eye, right_eye, _apply_eye_shape_left(comp_l), _apply_eye_shape_right(comp_r), outside_in=True)
            else:
                blit.blit_pil_to_both_async(left_eye, right_eye, _apply_eye_shape_left(eye_frame), _apply_eye_shape_right(eye_frame))

            time.sleep(max(0.0, frame_dt - (time.monotonic() - now)))

if __name__ == "__main__":
    try:
        run_eyes()
    except KeyboardInterrupt:
        pass
    finally:
        if left_eye is not None and right_eye is not None:
            try:
                overlay_l = render.render_blink_overlay(mirror=False)
                overlay_r = render.render_blink_overlay(mirror=True)
                if overlay_l and overlay_r:
                    blit.blit_pil_to_both(
                        left_eye, right_eye,
                        _apply_eye_shape_left(overlay_l), _apply_eye_shape_right(overlay_r),
                        reverse_rows=False, outside_in=False, inside_out=False, partial_rows=None,
                    )
            except Exception:
                pass
        sys.exit(0)