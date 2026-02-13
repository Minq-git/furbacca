"""
Furbacca vision: dual GC9A01 eyes using russhughes/gc9a01py (CPython compat layer).
Restored version with original state logic + NumPy performance optimizations.
"""
import json
import os
import socket
import sys
import time
import random

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
    arr = np.array(frame)
    masked_arr = shapes.apply_shape_mask_numpy(arr, config.get_eye_shape(), mirror=False)
    # Convert back to PIL Image so blit.py can handle it correctly
    from PIL import Image
    return Image.fromarray(masked_arr)

def _apply_eye_shape_right(frame):
    if frame is None: return frame
    # frame is a PIL Image; convert to array for NumPy masking
    arr = np.array(frame)
    masked_arr = shapes.apply_shape_mask_numpy(arr, config.get_eye_shape(), mirror=True)
    # Convert back to PIL Image so blit.py can handle it correctly
    from PIL import Image
    return Image.fromarray(masked_arr)

def run_eyes():
    if left_eye is None and right_eye is None:
        return

    print("👀 Furbacca Vision Online (Optimized).")
    # --- PRE-LOAD ASSETS ---
    # This happens before the animation engine starts
    render.preload_all_types()
    
    check_base = render.build_eye_base_sclera_iris()

    use_animated = (
        config.EYES_ANIMATED and not config.EYES_GRADIENT and not config.EYES_RAINBOW
        and assets.HAS_PIL and render.build_eye_base_sclera_iris() is not None
    )

    if use_animated:
        ANIM_FPS = int(os.environ.get("ANIM_FPS", "30"))
        print(f"  Animated eyes @ {ANIM_FPS} FPS. UDP enabled.")
        
        cached_eye_base_240 = render.build_eye_base_sclera_iris()
        frame_dt = 1.0 / ANIM_FPS
        
        # Original Easing Table
        EASE_TABLE = tuple(
            int(255.0 * (3.0 * (i / 255.0) ** 2 - 2.0 * (i / 255.0) ** 3))
            for i in range(256)
        )
        
        # --- Original State Machine ---
        pupil_x, pupil_y = 0.0, 0.0
        target_x, target_y = 0.0, 0.0
        eye_in_motion = False
        eye_old_x, eye_old_y = 0.0, 0.0
        eye_new_x, eye_new_y = 0.0, 0.0
        eye_move_start = 0.0
        eye_move_duration = 0.0
        eye_hold_until = 0.0
        IDLE_LOOK_TIMEOUT = 0.2
        MOVE_DURATION_MIN, MOVE_DURATION_MAX = 0.072, 0.144
        HOLD_DURATION_MAX = 3.0
        blit_open_bottom_to_top = False
        next_auto_blink = time.monotonic() + blink.next_auto_blink_delay()
        PUPIL_EASE = 0.48
        last_look_time = 0.0
        relaxed, focused, wide = config.eye_type_pupil_radii(config.get_eye_type())
        focus_until = 0.0
        wide_until = 0.0
        next_wide_at = 0.0
        FOCUS_HOLD_S = 0.35
        PUPIL_TRANSITION_S = 0.5
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
        last_impulse_at = 0.0
        SHIVER_DEBOUNCE_S = 0.28

        def _start_animation(name):
            nonlocal animation_segments, animation_start_time, animation_index
            nonlocal segment_start_x, segment_start_y, segment_end_x, segment_end_y
            animation_segments = animations.get_animation(name)
            if animation_segments:
                animation_start_time = time.monotonic()
                animation_index = 0
                segment_start_x, segment_start_y = pupil_x, pupil_y
                segment_end_x, segment_end_y = animation_segments[0][1], animation_segments[0][2]
                print(f"🎬 Animation: {name}")

        while True:
            now = time.monotonic()
            
            # --- UDP Command Logic (Original) ---
            while True:
                try:
                    data, _ = sock.recvfrom(1024)
                    msg = json.loads(data.decode())
                    action = msg.get("action")
                    if action == "blink":
                        if not animation_segments and animated_blink.can_trigger(now):
                            animated_blink.trigger(now)
                    elif action == "look":
                        tx, ty = msg.get("x"), msg.get("y")
                        if tx is not None: target_x = max(-1.0, min(1.0, float(tx)))
                        if ty is not None: target_y = max(-1.0, min(1.0, float(ty)))
                        last_look_time, focus_until = now, now + FOCUS_HOLD_S
                    elif action == "set_eye_shape":
                        shape = (msg.get("shape") or "round").strip().lower()
                        config.set_eye_shape(shape)
                    elif action == "set_eye_type":
                        eye_type = (msg.get("type") or msg.get("eye_type") or "default").strip().lower()
                        config.set_eye_type(eye_type)
    
                        # Refresh the cache with the new eye type textures
                        cached_eye_base_240 = render.build_eye_base_sclera_iris()
                        
                        # Reset pupil physics for the new type
                        relaxed, focused, wide = config.eye_type_pupil_radii(config.get_eye_type())
                        pupil_radius_current = float(relaxed)
                        print(f"👁 Eye type updated to: {config.get_eye_type()}")
                    elif action == "animation":
                        anim_name = (msg.get("name") or "").strip().lower()
                        if anim_name: _start_animation(anim_name)
                    elif action == "impulse":
                        if (now - last_impulse_at) >= SHIVER_DEBOUNCE_S:
                            last_impulse_at = now
                            _start_animation("shiver")
                except (BlockingIOError, json.JSONDecodeError):
                    break

            # --- 1. Auto-blink Trigger ---
            # Trigger ONLY if the timer is up and we aren't already blinking
            if not animation_segments and not animated_blink.is_closed and now >= next_auto_blink:
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
                elapsed = now - animation_start_time
                
                progress = min(1.0, max(0.0, elapsed / seg.duration)) if seg.duration > 0 else 1.0
                idx = min(255, int(progress * 255))
                e = EASE_TABLE[idx] / 255.0

                pupil_x = segment_start_x + (seg.x - segment_start_x) * e
                pupil_y = segment_start_y + (seg.y - segment_start_y) * e
                
                if elapsed >= seg.duration:
                    animation_index += 1
                    animation_start_time = now
                    if animation_index >= len(animation_segments):
                        animation_segments = []
                    else:
                        segment_start_x, segment_start_y = pupil_x, pupil_y
                        next_seg = animation_segments[animation_index]

                        segment_end_x, segment_end_y = next_seg.x, next_seg.y

            # --- Physics: Idle Looking & Pupil Radius ---
            relaxed, focused, wide = config.eye_type_pupil_radii(config.get_eye_type())
            if not animation_segments:
                if (now - last_look_time) <= IDLE_LOOK_TIMEOUT:
                    pupil_x += (target_x - pupil_x) * PUPIL_EASE
                    pupil_y += (target_y - pupil_y) * PUPIL_EASE
                else:
                    if eye_in_motion:
                        elapsed = now - eye_move_start
                        t = min(1.0, elapsed / eye_move_duration) if eye_move_duration > 0 else 1.0
                        e = EASE_TABLE[min(255, int(t * 255))] / 255.0
                        pupil_x = eye_old_x + (eye_new_x - eye_old_x) * e
                        pupil_y = eye_old_y + (eye_new_y - eye_old_y) * e
                        if elapsed >= eye_move_duration:
                            eye_in_motion = False
                            eye_hold_until = now + random.uniform(0.0, HOLD_DURATION_MAX)
                    elif now >= eye_hold_until:
                        eye_old_x, eye_old_y = pupil_x, pupil_y
                        eye_new_x, eye_new_y = random.uniform(-0.8, 0.8), random.uniform(-0.8, 0.8)
                        eye_move_start, eye_move_duration = now, random.uniform(MOVE_DURATION_MIN, MOVE_DURATION_MAX)
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
            transition_s = 0.06 if animation_segments else PUPIL_TRANSITION_S
            
            elapsed_r = now - radius_transition_start
            if elapsed_r >= transition_s or radius_transition_from == radius_transition_to:
                pupil_radius_current = float(radius_transition_to)
            else:
                # Smoothly ease the radius change
                progress = min(1.0, elapsed_r / transition_s)
                idx = min(255, int(progress * 255))
                e_r = EASE_TABLE[idx] / 255.0
                pupil_radius_current = radius_transition_from + (radius_transition_to - radius_transition_from) * e_r

            # --- Rendering & Async Blitting ---
            eye_frame = render.render_animated_frame(cached_eye_base_240, pupil_x, pupil_y, "open", pupil_radius=pupil_radius_current)
            
            if blit_open_bottom_to_top:
                blit.blit_pil_to_both_async(left_eye, right_eye, _apply_eye_shape_left(eye_frame), _apply_eye_shape_right(eye_frame), inside_out=True)
                blit_open_bottom_to_top = False
            elif animated_blink.is_closed:
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
    run_eyes()