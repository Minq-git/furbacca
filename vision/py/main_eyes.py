"""
Furbacca vision: dual GC9A01 eyes using russhughes/gc9a01py (CPython compat layer).
Restored version with original state logic + NumPy performance optimizations.
"""

from __future__ import annotations

import os
import signal
import sys
import threading
import time
from types import FrameType

_shutdown_requested = False


def _handle_shutdown(_signum: int | signal.Signals | None, _frame: FrameType | None) -> None:
    global _shutdown_requested
    _shutdown_requested = True


try:
    import numpy as np
    from numpy import ndarray
except ImportError:
    np = None
    ndarray = None

import vision.py.messages as messages  # noqa: E402
from synapses.py.receiver import SynapseReceiver  # noqa: E402
from vision.py.assets import config, loaders  # noqa: E402
from vision.py.engine import render  # noqa: E402
from vision.py.engine.render_engine import RenderEngine  # noqa: E402
from vision.py.engine.state import FurbaccaState  # noqa: E402
from vision.py.hardware.gc9a01_display import GC9A01_Display  # noqa: E402

# Re-export for callers
get_eye_type = config.get_eye_type
set_eye_type = config.set_eye_type

# UDP bridge (receiver binds in run_eyes)
UDP_BIND = os.environ.get("UDP_BIND", "127.0.0.1").strip() or "127.0.0.1"
UDP_PORT = 5005


def run_eyes() -> None:
    print(messages.get("eyes", "booting"))

    hardware = GC9A01_Display(swap_left_right=config.SWAP_LEFT_RIGHT_SPI)
    try:
        hardware.init_displays()
    except Exception as e:
        print(messages.get("eyes", "display_init_failed", error=str(e)))
        return

    if not hardware.is_ready():
        return

    # Pre-load other eye types in background; current type loads on first frame (faster startup)
    _current_type = config.get_eye_type()
    _preload_thread = threading.Thread(
        target=lambda: render.preload_all_types(skip_type=_current_type),
        daemon=True,
    )
    _preload_thread.start()

    use_animated = config.EYES_ANIMATED and not config.EYES_GRADIENT and not config.EYES_RAINBOW and loaders.HAS_PIL

    if use_animated:
        engine = RenderEngine(fps=config.ANIM_FPS)
        print(messages.get("eyes", "opening_animated", fps=config.ANIM_FPS))

        receiver = SynapseReceiver(
            port=UDP_PORT,
            bind=UDP_BIND,
            recv_size=config.UDP_RECV_SIZE,
        )
        print(messages.get("eyes", "udp_bind", bind=UDP_BIND, port=UDP_PORT))
        print(messages.get("eyes", "listening"))

        state = FurbaccaState()

        # One synchronous frame so both displays get a stable image before async (reduces right-eye crash at startup)
        t0 = time.monotonic()
        state.tick(t0)
        plan0 = engine.generate_frame(state, t0)
        hardware.blit(plan0, inside_out=plan0.inside_out, outside_in=plan0.outside_in, sync=True)

        _ = signal.signal(signal.SIGINT, _handle_shutdown)
        _ = signal.signal(signal.SIGTERM, _handle_shutdown)

        while True:
            if _shutdown_requested:
                break

            frame_started_at = time.monotonic()

            while True:
                cmd = receiver.poll()
                if cmd is None:
                    break
                state.update(cmd, frame_started_at)

                if state.restart_requested:
                    ok = hardware.restart_displays()
                    if ok:
                        state.on_restart_succeeded(frame_started_at)
                        print(messages.get("eyes", "restarting_eyes"))
                    else:
                        state.on_restart_failed()
                        print(messages.get("eyes", "restart_both_failed"))

            state.tick(frame_started_at)
            plan = engine.generate_frame(state, frame_started_at)
            hardware.blit(plan, inside_out=plan.inside_out, outside_in=plan.outside_in)
            engine.sleep_until_next_frame(frame_started_at)


if __name__ == "__main__":
    try:
        run_eyes()
    except KeyboardInterrupt:
        pass
    finally:
        # Best-effort blanking: leave closed lids on both panels.
        try:
            hardware = GC9A01_Display(swap_left_right=config.SWAP_LEFT_RIGHT_SPI)
            hardware.init_displays()
            overlay_l = render.render_blink_overlay(mirror=False)
            overlay_r = render.render_blink_overlay(mirror=True)
            if overlay_l and overlay_r:
                from engine.render_engine import FramePlan

                hardware.blit(FramePlan(left=overlay_l, right=overlay_r), sync=True)
        except Exception:
            pass
        sys.exit(0)
