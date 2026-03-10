#!/usr/bin/env python3
"""
Furbacca live eye alignment: dial in pupil offsets on the SPI displays without restarting the nervous system.
Run from repo root: python3 -m vision.py.tune_eyes

Updates config.PUPIL_OFFSET_* in memory and re-renders with gaze at (0, 0). At exit prints .env lines to copy.
"""

from __future__ import annotations

import sys
import time

from vision.py.assets import config
from vision.py.engine.render_engine import RenderEngine
from vision.py.engine.state import FrameIntent, FurbaccaState
from vision.py.hardware.gc9a01_display import GC9A01_Display


def _render_center(
    hardware: GC9A01_Display,
    engine: RenderEngine,
    state: FurbaccaState,
) -> None:
    """Render open eyes with gaze fixed at center; no blink or idle wander (tuning-only)."""
    now = time.monotonic()
    # Set only what the renderer needs; do not call tick() so blink and idle wander stay off
    state.frame_intent = FrameIntent(kind="open")
    state.pupil_x = 0.0
    state.pupil_y = 0.0
    relaxed_r, _f, _w = config.eye_type_pupil_radii(config.get_eye_type())
    state.pupil_radius_current = float(int(relaxed_r))
    plan = engine.generate_frame(state, now)
    hardware.blit(plan, inside_out=plan.inside_out, outside_in=plan.outside_in, sync=True)


def main() -> int:
    print("Waking up Furbacca's visual cortex for tuning...")

    hardware = GC9A01_Display(swap_left_right=config.SWAP_LEFT_RIGHT_SPI)
    try:
        hardware.init_displays()
    except Exception as e:
        print(f"Display init failed: {e}")
        return 1

    if not hardware.is_ready():
        print("Displays not ready.")
        return 1

    engine = RenderEngine(fps=config.ANIM_FPS)
    state = FurbaccaState()

    _render_center(hardware, engine, state)

    print("\n========================================")
    print(" Furbacca Live Eye Alignment Tool")
    print("========================================")
    print("Enter offsets as comma-separated decimals: X, Y")
    print("  +X = Right  |  -X = Left")
    print("  +Y = Down   |  -Y = Up")
    print("Example: 0.15, 0.1")
    print("Press Enter to keep current; type 'q' to quit and print .env lines.\n")

    while True:
        try:
            left_val = input(f"Left Eye (X, Y) [current: {config.PUPIL_OFFSET_LEFT_X}, {config.PUPIL_OFFSET_LEFT_Y}]: ")
            if left_val.strip().lower() == "q":
                break
            if left_val.strip():
                lx, ly = map(float, left_val.replace(" ", "").split(","))
                config.PUPIL_OFFSET_LEFT_X = lx
                config.PUPIL_OFFSET_LEFT_Y = ly

            right_val = input(
                f"Right Eye (X, Y) [current: {config.PUPIL_OFFSET_RIGHT_X}, {config.PUPIL_OFFSET_RIGHT_Y}]: "
            )
            if right_val.strip().lower() == "q":
                break
            if right_val.strip():
                rx, ry = map(float, right_val.replace(" ", "").split(","))
                config.PUPIL_OFFSET_RIGHT_X = rx
                config.PUPIL_OFFSET_RIGHT_Y = ry

            print("--> Pushing new offsets to displays...")
            _render_center(hardware, engine, state)

        except ValueError:
            print("[!] Invalid format. Use two numbers separated by a comma (e.g. 0.15, 0.1).")
        except (KeyboardInterrupt, EOFError):
            break

    print("\n========================================")
    print("Add to your .env file:")
    print("========================================")
    print(f"FURBACCA_PUPIL_OFFSET_LEFT_X={config.PUPIL_OFFSET_LEFT_X}")
    print(f"FURBACCA_PUPIL_OFFSET_LEFT_Y={config.PUPIL_OFFSET_LEFT_Y}")
    print(f"FURBACCA_PUPIL_OFFSET_RIGHT_X={config.PUPIL_OFFSET_RIGHT_X}")
    print(f"FURBACCA_PUPIL_OFFSET_RIGHT_Y={config.PUPIL_OFFSET_RIGHT_Y}")
    print("========================================\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
