"""
Furbacca vision: dual GC9A01 eyes using russhughes/gc9a01py (CPython compat layer).
Orchestrates display init, UDP bridge, and run loop; delegates to config, assets, render, blit, test_patterns.
"""
import json
import os
import socket
import sys
import time

_vision_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _vision_dir)

import config
import assets
import blit
import render
import shapes
import test_patterns
from display import init_displays

# Re-export for callers that do "from vision.eyes import get_eye_type"
get_eye_type = config.get_eye_type
set_eye_type = config.set_eye_type

# Display handles (set on init)
left_eye, right_eye = None, None
try:
    left_eye, right_eye = init_displays(swap_left_right=config.SWAP_LEFT_RIGHT_SPI)
except Exception as e:
    print(f"⚠ Display init failed: {e}")
    import traceback
    traceback.print_exc()

# UDP bridge
UDP_IP = "127.0.0.1"
UDP_PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((UDP_IP, UDP_PORT))
sock.setblocking(False)

# --- Optional: /dev/fb1 fallback (legacy) ---
FB1_PATH = "/dev/fb1"
_fb1_warned = False

def _write_fb1(row_buf_or_full_buffer):
    """Write buffer (row or full frame) to /dev/fb1. LE RGB565. Needs sudo for /dev/fb1."""
    global _fb1_warned
    try:
        with open(FB1_PATH, "wb") as fb:
            if isinstance(row_buf_or_full_buffer, (list, tuple)):
                for row in row_buf_or_full_buffer:
                    fb.write(row)
            else:
                fb.write(row_buf_or_full_buffer)
    except PermissionError:
        if not _fb1_warned:
            print("⚠ Left eye (fb1): run with sudo for /dev/fb1 write access.")
            _fb1_warned = True
    except Exception as e:
        print(f"⚠ fb1 write error: {e}")

def show_eye_image_fb1():
    """Draw eye image to /dev/fb1 (left eye when overlay is used). LE RGB565."""
    img = assets.load_eye_image()
    if img is None:
        return
    try:
        import struct
        img = img.rotate(180)
        rows = []
        for y in range(config.EYE_SIZE):
            row_buf = bytearray(config.EYE_SIZE * 2)
            for x in range(config.EYE_SIZE):
                r, g, b = img.getpixel((x, y))
                c565 = (r & 0xF8) << 8 | (g & 0xFC) << 3 | (b >> 3)
                row_buf[x * 2 : x * 2 + 2] = struct.pack("<H", c565)
            rows.append(row_buf)
        _write_fb1(rows)
    except Exception as e:
        print(f"⚠ Show image fb1 error: {e}")

def fill_fb1(color_565):
    """Fill /dev/fb1 with solid color (16-bit RGB565, little-endian)."""
    import struct
    row = struct.pack("<H", color_565) * config.EYE_SIZE
    _write_fb1([row] * config.EYE_SIZE)


def show_eye_image(display):
    """Send PIL image to gc9a01py display. Big-endian RGB565 row-by-row."""
    img = assets.load_eye_image()
    if img is None or display is None:
        return
    try:
        blit.blit_pil_to_display(display, img)
    except Exception as e:
        print(f"⚠ Show image error: {e}")


def _apply_eye_shape(frame):
    """Apply eye shape mask on top of frame (layer above sclera/iris/pupil). Outside shape = black."""
    if frame is None:
        return frame
    return shapes.apply_shape_mask(frame, config.get_eye_shape())


def show_constructed_eye():
    """Show the static constructed eyeball (sclera + iris + pupil at center) on both displays."""
    frame = render.render_animated_frame(render.build_eye_base_sclera_iris(), 0.0, 0.0, "open")
    if frame is not None:
        blit.blit_pil_to_both(left_eye, right_eye, _apply_eye_shape(frame), reverse_rows=False, outside_in=False, inside_out=False, partial_rows=None)
    else:
        show_eye_image(left_eye)
        if right_eye is not None:
            time.sleep(0.02)
            show_eye_image(right_eye)


def run_eyes():
    if left_eye is None and right_eye is None:
        print("❌ No displays initialized. Run scripts/fetch-gc9a01py.sh and ensure vision/machine_compat and vision/gc9a01py are present.")
        return

    print("👀 Furbacca Vision Online (gc9a01py).")
    use_gradient = config.EYES_GRADIENT
    use_rainbow = config.EYES_RAINBOW
    # Gradient/rainbow take precedence over animated; otherwise EYES_RAINBOW=1 would still show animated eyes
    use_animated = (
        config.EYES_ANIMATED and not use_gradient and not use_rainbow
        and assets.HAS_PIL and render.build_eye_base_sclera_iris() is not None
    )
    use_image = not config.EYES_SOLID_COLORS and not use_gradient and not use_rainbow and not use_animated and (
        render.build_eye_base_sclera_iris() is not None or assets.load_eye_image() is not None
    )

    def _show_idle():
        if use_gradient:
            test_patterns.show_gradient(left_eye)
            time.sleep(0.05)
            test_patterns.show_gradient(right_eye)
        elif use_rainbow:
            test_patterns.show_rainbow(left_eye)
            time.sleep(0.05)
            test_patterns.show_rainbow(right_eye)
        elif use_image:
            show_constructed_eye()
        else:
            if left_eye:
                left_eye.fill(0xF800)
            if right_eye:
                right_eye.fill(0x001F)

    if use_animated:
        print("  Animated eyes (headless, no monitor). UDP: blink, look x/y.")
        import random
        cached_eye_base_240 = render.build_eye_base_sclera_iris()
        EASE_TABLE = tuple(
            int(255.0 * (3.0 * (i / 255.0) ** 2 - 2.0 * (i / 255.0) ** 3))
            for i in range(256)
        )
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
        next_auto_blink = time.monotonic() + random.uniform(2.0, 5.0)
        ANIM_FPS = int(os.environ.get("ANIM_FPS", "60"))
        frame_dt = 1.0 / ANIM_FPS
        PUPIL_EASE = 0.48
        BLINK_DEBOUNCE_S = 0.2
        CYCLE_EYE_TYPE_DEBOUNCE_S = 0.4
        last_blink_end = 0.0
        last_cycle_eye_type_at = 0.0
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
        blink_phase = None
        blink_start_time = 0.0
        closing_duration_s = 0.05
        CLOSING_S_MIN, CLOSING_S_MAX = 0.04, 0.07
        do_cycle_on_next_open = False
        animation_segments = []
        animation_start_time = 0.0
        animation_index = 0
        segment_start_x, segment_start_y = 0.0, 0.0
        segment_end_x, segment_end_y = 0.0, 0.0

        def _start_animation(name):
            nonlocal animation_segments, animation_start_time, animation_index
            nonlocal segment_start_x, segment_start_y, segment_end_x, segment_end_y
            if name == "nervous_look":
                n = random.randint(2, 3)
                animation_segments = [(0.28, -5, 0.0), (0.28, 5, 0.0)] * n
                animation_start_time = time.monotonic()
                animation_index = 0
                segment_start_x, segment_start_y = pupil_x, pupil_y
                segment_end_x, segment_end_y = animation_segments[0][1], animation_segments[0][2]
                print("🎬 Animation: nervous_look")
            else:
                animation_segments = []

        def do_blink():
            nonlocal blink_phase, blink_start_time, closing_duration_s
            blink_phase = "closing"
            blink_start_time = time.monotonic()
            closing_duration_s = random.uniform(CLOSING_S_MIN, CLOSING_S_MAX)

        while True:
            now = time.monotonic()
            while True:
                try:
                    data, _ = sock.recvfrom(1024)
                    msg = json.loads(data.decode())
                    action = msg.get("action")
                    if action == "blink":
                        if now - last_blink_end >= BLINK_DEBOUNCE_S:
                            do_blink()
                            last_blink_end = now
                            print("🐾 Logic: Blinked both eyes.")
                    elif action == "look":
                        tx = msg.get("x")
                        ty = msg.get("y")
                        if tx is not None:
                            target_x = max(-1.0, min(1.0, float(tx)))
                        if ty is not None:
                            target_y = max(-1.0, min(1.0, float(ty)))
                        last_look_time = now
                        focus_until = now + FOCUS_HOLD_S
                    elif action == "cycle_eye_type":
                        if now - last_cycle_eye_type_at >= CYCLE_EYE_TYPE_DEBOUNCE_S:
                            last_cycle_eye_type_at = now
                            do_cycle_on_next_open = True
                            do_blink()
                    elif action == "animation":
                        anim_name = (msg.get("name") or msg.get("animation") or "").strip().lower()
                        if anim_name:
                            _start_animation(anim_name)
                except BlockingIOError:
                    break
                except json.JSONDecodeError:
                    pass

            if blink_phase is None and now >= next_auto_blink:
                do_blink()
                next_auto_blink = now + random.uniform(2.0, 5.0)

            if blink_phase == "closing":
                if (now - blink_start_time) >= closing_duration_s:
                    blink_phase = None
                    blit_open_bottom_to_top = True
                    if do_cycle_on_next_open:
                        do_cycle_on_next_open = False
                        config.cycle_eye_type()
                        print(f"👁 Eye type: {config.get_eye_type()}")
                    total_blink_s = now - blink_start_time
                    next_auto_blink = now + (total_blink_s * 3.0) + random.uniform(0.0, 4.0)

            blink_state = "open" if blink_phase is None else "closed"

            if animation_segments:
                seg = animation_segments[animation_index]
                elapsed = now - animation_start_time
                progress = min(1.0, elapsed / seg[0])
                idx = min(255, int(progress * 255))
                e = EASE_TABLE[idx] / 255.0
                pupil_x = segment_start_x + (segment_end_x - segment_start_x) * e
                pupil_y = segment_start_y + (segment_end_y - segment_start_y) * e
                pupil_x = max(-1.0, min(1.0, pupil_x))
                pupil_y = max(-1.0, min(1.0, pupil_y))
                if elapsed >= seg[0]:
                    animation_index += 1
                    animation_start_time = now
                    if animation_index >= len(animation_segments):
                        animation_segments = []
                        animation_index = 0
                    else:
                        segment_start_x, segment_start_y = pupil_x, pupil_y
                        next_seg = animation_segments[animation_index]
                        segment_end_x, segment_end_y = next_seg[1], next_seg[2]
            elif (now - last_look_time) <= IDLE_LOOK_TIMEOUT:
                pupil_x += (target_x - pupil_x) * PUPIL_EASE
                pupil_y += (target_y - pupil_y) * PUPIL_EASE
                pupil_x = max(-1.0, min(1.0, pupil_x))
                pupil_y = max(-1.0, min(1.0, pupil_y))
            else:
                if eye_in_motion:
                    elapsed = now - eye_move_start
                    if elapsed >= eye_move_duration:
                        eye_in_motion = False
                        pupil_x = eye_old_x = eye_new_x
                        pupil_y = eye_old_y = eye_new_y
                        eye_hold_until = now + random.uniform(0.0, HOLD_DURATION_MAX)
                        focus_until = now + FOCUS_HOLD_S
                    else:
                        t = elapsed / eye_move_duration
                        idx = min(255, int(t * 255))
                        e = EASE_TABLE[idx] / 255.0
                        pupil_x = eye_old_x + (eye_new_x - eye_old_x) * e
                        pupil_y = eye_old_y + (eye_new_y - eye_old_y) * e
                else:
                    pupil_x = eye_old_x
                    pupil_y = eye_old_y
                    if now >= eye_hold_until:
                        while True:
                            dx = random.uniform(-1.0, 1.0)
                            dy = random.uniform(-1.0, 1.0)
                            if dx * dx + dy * dy <= 1.0:
                                break
                        eye_old_x, eye_old_y = pupil_x, pupil_y
                        eye_new_x, eye_new_y = dx * 0.85, dy * 0.85
                        eye_move_start = now
                        eye_move_duration = random.uniform(MOVE_DURATION_MIN, MOVE_DURATION_MAX)
                        eye_in_motion = True
                pupil_x = max(-1.0, min(1.0, pupil_x))
                pupil_y = max(-1.0, min(1.0, pupil_y))

            relaxed, focused, wide = config.eye_type_pupil_radii(config.get_eye_type())
            if now < focus_until:
                pupil_radius_target = focused
            elif now < wide_until:
                pupil_radius_target = wide
            else:
                pupil_radius_target = relaxed
            if next_wide_at == 0.0:
                next_wide_at = now + random.uniform(25.0, 45.0)
            if now >= next_wide_at and pupil_radius_target == relaxed:
                wide_until = now + random.uniform(1.0, 2.0)
                next_wide_at = now + random.uniform(25.0, 45.0)
            if pupil_radius_target != radius_transition_to:
                radius_transition_from = pupil_radius_current
                radius_transition_to = pupil_radius_target
                radius_transition_start = now
            elapsed = now - radius_transition_start
            if elapsed >= PUPIL_TRANSITION_S or radius_transition_from == radius_transition_to:
                pupil_radius_current = float(radius_transition_to)
            else:
                progress = elapsed / PUPIL_TRANSITION_S
                idx = min(255, int(progress * 255))
                e = EASE_TABLE[idx] / 255.0
                pupil_radius_current = radius_transition_from + (radius_transition_to - radius_transition_from) * e
            pupil_radius = pupil_radius_current

            eye_frame = render.render_animated_frame(cached_eye_base_240, pupil_x, pupil_y, "open", pupil_radius=pupil_radius)
            if blit_open_bottom_to_top:
                blit.blit_pil_to_both(left_eye, right_eye, _apply_eye_shape(eye_frame), reverse_rows=False, outside_in=False, inside_out=True, partial_rows=None)
                blit_open_bottom_to_top = False
            elif blink_state == "closed":
                overlay = render.render_blink_overlay()
                if overlay is not None:
                    composite = eye_frame.copy()
                    composite.paste(overlay, (0, 0))
                    blit.blit_pil_to_both(left_eye, right_eye, _apply_eye_shape(composite), reverse_rows=False, outside_in=True, inside_out=False, partial_rows=None)
                else:
                    blit.blit_pil_to_both(left_eye, right_eye, _apply_eye_shape(eye_frame), reverse_rows=False, outside_in=False, inside_out=False, partial_rows=None)
            else:
                blit.blit_pil_to_both(left_eye, right_eye, _apply_eye_shape(eye_frame), reverse_rows=False, outside_in=False, inside_out=False, partial_rows=None)
            time.sleep(max(0.0, frame_dt - (time.monotonic() - now)))
        return

    if use_gradient:
        print("  Showing XY gradient on both displays (EYES_GRADIENT=1).")
        _show_idle()
        while True:
            try:
                sock.recvfrom(1024)
            except BlockingIOError:
                pass
            time.sleep(0.02)
    elif use_rainbow:
        print("  Showing rainbow on both displays (EYES_RAINBOW=1).")
        _show_idle()
        while True:
            try:
                sock.recvfrom(1024)
            except BlockingIOError:
                pass
            time.sleep(0.02)
    elif use_image:
        print("  Showing eye image on both displays...")
        _show_idle()
    else:
        if config.EYES_SOLID_COLORS:
            print("  Solid colors only (EYES_SOLID_COLORS=1).")
        if left_eye:
            left_eye.fill(0xF800)
        time.sleep(0.02)
        if right_eye:
            right_eye.fill(0x001F)

    # Static blink loop (image or solid-color mode)
    _static_eye_frame = _apply_eye_shape(render.render_animated_frame(render.build_eye_base_sclera_iris(), 0.0, 0.0, "open"))
    BLINK_DEBOUNCE_S = 0.2
    CYCLE_EYE_TYPE_DEBOUNCE_S = 0.4
    last_blink_end = 0.0
    last_cycle_eye_type_at = 0.0
    cycle_on_next_open = False
    blink_phase = None

    while True:
        now = time.monotonic()
        while True:
            try:
                data, _ = sock.recvfrom(1024)
                msg = json.loads(data.decode())
                action = msg.get("action")
                if action == "blink" and (now - last_blink_end) >= BLINK_DEBOUNCE_S:
                    blink_phase = "closing"
                    last_blink_end = now
                    print("🐾 Logic: Blinked both eyes.")
                elif action == "cycle_eye_type" and (now - last_cycle_eye_type_at) >= CYCLE_EYE_TYPE_DEBOUNCE_S:
                    last_cycle_eye_type_at = now
                    cycle_on_next_open = True
                    blink_phase = "closing"
                    last_blink_end = now
            except BlockingIOError:
                break
            except json.JSONDecodeError:
                pass

        if blink_phase == "closing":
            if _static_eye_frame is not None:
                blit.blit_pil_to_both(left_eye, right_eye, _static_eye_frame, reverse_rows=False, outside_in=False, inside_out=False, partial_rows=None)
            overlay = render.render_blink_overlay()
            if overlay is not None:
                blit.blit_pil_to_both(left_eye, right_eye, _apply_eye_shape(overlay), reverse_rows=False, outside_in=True, inside_out=False, partial_rows=None)
            blink_phase = "opening"
        elif blink_phase == "opening":
            if cycle_on_next_open:
                cycle_on_next_open = False
                config.cycle_eye_type()
                _static_eye_frame = _apply_eye_shape(render.render_animated_frame(render.build_eye_base_sclera_iris(), 0.0, 0.0, "open"))
                print(f"👁 Eye type: {config.get_eye_type()}")
            if _static_eye_frame is not None:
                blit.blit_pil_to_both(left_eye, right_eye, _static_eye_frame, reverse_rows=False, outside_in=False, inside_out=True, partial_rows=None)
            blink_phase = None

        time.sleep(0.02)


if __name__ == "__main__":
    run_eyes()
