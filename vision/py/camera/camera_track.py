#!/usr/bin/env python3
"""
Furbacca eye tracking: Picamera2 + IMX500 object detection → UDP "look x y" to eyes.
"""

from __future__ import annotations

# ruff: noqa: I001

import argparse
import os
import socket
import sys
import time
from collections.abc import Mapping, Sequence
from typing import Protocol, cast

# Synapses shared contract (UDP message shapes)
from synapses.py.vision_messages import EyeTrackingEvent, LookCommand  # noqa: E402

# Picamera2 + OpenCV are system-installed on the Pi
try:
    from picamera2 import Picamera2 as _Picamera2  # pyright: ignore[reportMissingImports,reportUnknownVariableType]
    from picamera2.devices import IMX500 as _IMX500  # pyright: ignore[reportMissingImports,reportUnknownVariableType]
    from picamera2.devices.imx500 import NetworkIntrinsics as _NetworkIntrinsics  # pyright: ignore[reportMissingImports,reportUnknownVariableType]
except ImportError as e:
    err = str(e).lower()
    if "cv2" in err or "opencv" in err:
        print("OpenCV (cv2) not found. On the Pi: sudo apt install -y python3-opencv", file=sys.stderr)
    else:
        print("picamera2 not found. On the Pi: sudo apt install -y python3-picamera2", file=sys.stderr)
    print(f"  ImportError: {e}", file=sys.stderr)
    sys.exit(1)

UDP_PORT = 5005
NS_EVENTS_PORT = 5006  # nervous system: looking_started / looking_stopped
# COCO: 0 = person (prefer for tracking)
PERSON_CLASS_ID = 0
# Gaze invert: displays are blit-flipped 180° so "person left" must become "eyes look left"
TRACKING_INVERT_X = os.environ.get("FURBACCA_TRACKING_INVERT_X", "1").strip().lower() in ("1", "true", "yes")
TRACKING_INVERT_Y = os.environ.get("FURBACCA_TRACKING_INVERT_Y", "1").strip().lower() in ("1", "true", "yes")

Detection = tuple[float, float, int, float]  # (cx, cy, class_id, confidence)
Target = tuple[float, float, float, int]  # (cx, cy, conf, cls)


class _NetworkIntrinsicsLike(Protocol):
    task: str
    inference_rate: int
    preserve_aspect_ratio: bool
    bbox_normalization: bool
    bbox_order: str
    labels: Sequence[str] | None

    def update_with_defaults(self) -> None: ...


class _Picamera2Like(Protocol):
    def create_preview_configuration(
        self,
        *,
        main: Mapping[str, object],
        controls: Mapping[str, object],
        buffer_count: int,
    ) -> object: ...

    def start(self, config: object, show_preview: bool = False) -> None: ...

    def capture_metadata(self) -> Mapping[str, object]: ...

    def camera_configuration(self) -> Mapping[str, object]: ...

    def stop(self) -> None: ...


class _IMX500Like(Protocol):
    camera_num: int
    network_intrinsics: _NetworkIntrinsicsLike | None

    def get_outputs(self, metadata: Mapping[str, object], *, add_batch: bool = True) -> object | None: ...

    def get_input_size(self) -> tuple[int, int]: ...

    def convert_inference_coords(
        self,
        coords: tuple[float, float, float, float],
        metadata: Mapping[str, object],
        picam2: _Picamera2Like,
        *,
        stream: str = "main",
    ) -> tuple[float, float, float, float]: ...

    def show_network_fw_progress_bar(self) -> None: ...

    def set_auto_aspect_ratio(self) -> None: ...


def parse_detections(
    imx500: _IMX500Like,
    picam2: _Picamera2Like,
    intrinsics: _NetworkIntrinsicsLike,
    metadata: Mapping[str, object],
    threshold: float = 0.5,
) -> list[Detection]:
    """Return list of (center_x, center_y, class_id, confidence) in ISP output pixel coords."""
    np_outputs = imx500.get_outputs(metadata, add_batch=True)
    if np_outputs is None:
        return []

    # Picamera2 returns NumPy arrays, but we treat them as plain sequences here
    # so we can type everything without relying on NumPy stubs.
    outs = cast(tuple[object, object, object], np_outputs)
    boxes_batch = cast(Sequence[Sequence[Sequence[float]]], outs[0])
    scores_batch = cast(Sequence[Sequence[float]], outs[1])
    classes_batch = cast(Sequence[Sequence[float]], outs[2])

    boxes_rows: list[tuple[float, float, float, float]] = [
        (float(row[0]), float(row[1]), float(row[2]), float(row[3])) for row in boxes_batch[0]
    ]
    scores_vals: list[float] = [float(s) for s in scores_batch[0]]
    classes_vals: list[int] = [int(c) for c in classes_batch[0]]

    _input_w, input_h = imx500.get_input_size()
    if intrinsics.bbox_normalization and input_h:
        boxes_rows = [(y0 / input_h, x0 / input_h, y1 / input_h, x1 / input_h) for (y0, x0, y1, x1) in boxes_rows]
    if intrinsics.bbox_order == "xy":
        boxes_rows = [(x0, y0, x1, y1) for (y0, x0, y1, x1) in boxes_rows]

    out: list[Detection] = []
    for box, score_f, cls in zip(boxes_rows, scores_vals, classes_vals):
        if score_f < threshold:
            continue
        y0, x0, y1, x1 = box
        coords = (float(y0), float(x0), float(y1), float(x1))
        rect = imx500.convert_inference_coords(coords, metadata, picam2, stream="main")
        x, y, w, h = rect
        cx = x + w / 2
        cy = y + h / 2
        out.append((cx, cy, int(cls), score_f))
    return out


def pick_target(
    detections: list[Detection],
    prefer_class: int = PERSON_CLASS_ID,
) -> Target | None:
    """Choose one detection: prefer prefer_class (person), else highest confidence."""
    if not detections:
        return None
    person: list[Detection] = [d for d in detections if d[2] == prefer_class]
    if person:
        best: Detection = max(person, key=lambda d: d[3])
    else:
        best = max(detections, key=lambda d: d[3])
    return (best[0], best[1], best[3], best[2])


def center_to_normalized(cx: float, cy: float, width: float, height: float) -> tuple[float, float]:
    """Map pixel center (cx, cy) to normalized x, y in [-1, 1]. Center of frame = (0, 0)."""
    if width <= 0 or height <= 0:
        return 0.0, 0.0
    nx = (cx / width - 0.5) * 2.0
    ny = (cy / height - 0.5) * 2.0
    return max(-1.0, min(1.0, nx)), max(-1.0, min(1.0, ny))


def main() -> None:
    ap = argparse.ArgumentParser(description="Furbacca camera tracking: IMX500 → UDP look to eyes")
    _ = ap.add_argument(
        "--model",
        default="/usr/share/imx500-models/imx500_network_ssd_mobilenetv2_fpnlite_320x320_pp.rpk",
        help="IMX500 model (.rpk)",
    )
    _ = ap.add_argument("--host", default="127.0.0.1", help="UDP host for eyes (default 127.0.0.1)")
    _ = ap.add_argument("--port", type=int, default=UDP_PORT, help=f"UDP port (default {UDP_PORT})")
    _ = ap.add_argument("--threshold", type=float, default=0.5, help="Detection confidence threshold")
    _ = ap.add_argument("--smooth", type=float, default=0.5, help="EMA smoothing 0..1 (0=no smooth, 1=no movement)")
    _ = ap.add_argument("--print-every", type=int, default=0, help="Print detections every N frames (0=off)")
    _ = ap.add_argument("--no-preview", action="store_true", default=True, help="No display (default on)")
    args = ap.parse_args()

    host: str = cast(str, args.host)
    port: int = cast(int, args.port)
    threshold: float = cast(float, args.threshold)
    smooth: float = cast(float, args.smooth)
    print_every: int = cast(int, args.print_every)
    model_path: str = cast(str, args.model)

    # IMX500 must be created before Picamera2
    imx500 = cast(_IMX500Like, _IMX500(model_path))
    intrinsics = imx500.network_intrinsics
    if not intrinsics:
        intrinsics = cast(_NetworkIntrinsicsLike, _NetworkIntrinsics())
        intrinsics.task = "object detection"
    elif intrinsics.task != "object detection":
        print("Model is not object detection.", file=sys.stderr)
        sys.exit(1)
    intrinsics.update_with_defaults()

    picam2 = cast(_Picamera2Like, _Picamera2(imx500.camera_num))
    config = picam2.create_preview_configuration(
        main={"size": (640, 480)},
        controls={"FrameRate": int(intrinsics.inference_rate) if intrinsics.inference_rate else 15},
        buffer_count=6,
    )
    imx500.show_network_fw_progress_bar()
    picam2.start(config, show_preview=False)
    if intrinsics.preserve_aspect_ratio:
        imx500.set_auto_aspect_ratio()

    width: int = 640
    height: int = 480
    try:
        main_config = picam2.camera_configuration()
        main_section = main_config.get("main")
        if isinstance(main_section, dict):
            main_section_t = cast(dict[str, object], main_section)
            main_size = main_section_t.get("size")
            if isinstance(main_size, (list, tuple)) and len(main_size) >= 2:
                width, height = int(main_size[0]), int(main_size[1])
    except Exception:
        pass

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    labels: list[str] = list(intrinsics.labels or [])

    smooth_x, smooth_y = 0.0, 0.0
    frame = 0
    was_looking = False
    last_looking_at_sent = 0.0  # throttle "looking_at" events to NS (~every 2s)
    print(
        f"Camera tracking → UDP {host}:{port} (smooth={smooth}, threshold={threshold}, invert_x={TRACKING_INVERT_X}, invert_y={TRACKING_INVERT_Y})",
        file=sys.stderr,
    )
    print("Ctrl+C to stop.", file=sys.stderr)

    try:
        while True:
            metadata = picam2.capture_metadata()
            detections: list[Detection] = parse_detections(imx500, picam2, intrinsics, metadata, threshold=threshold)
            frame += 1

            if print_every and frame % print_every == 0 and detections:
                for cx, cy, cls, conf in detections:
                    label = labels[cls] if cls < len(labels) else str(cls)
                    print(f"  [{frame}] {label} {conf:.2f} at ({cx:.0f}, {cy:.0f})")

            target: Target | None = pick_target(detections)
            if target is None:
                if was_looking:
                    try:
                        ev = EyeTrackingEvent(event="looking_stopped")
                        _ = sock.sendto(ev.to_json().encode(), ("127.0.0.1", NS_EVENTS_PORT))
                    except OSError:
                        pass
                    was_looking = False
                continue
            cx, cy, conf, cls = target
            label = labels[cls] if cls < len(labels) else str(cls)
            nx, ny = center_to_normalized(cx, cy, width, height)

            if not was_looking:
                try:
                    ev = EyeTrackingEvent(event="looking_started")
                    _ = sock.sendto(ev.to_json().encode(), ("127.0.0.1", NS_EVENTS_PORT))
                except OSError:
                    pass
                was_looking = True

            # EMA smoothing
            alpha: float = 1.0 - smooth
            smooth_x = alpha * smooth_x + (1 - alpha) * nx
            smooth_y = alpha * smooth_y + (1 - alpha) * ny

            send_x = -smooth_x if TRACKING_INVERT_X else smooth_x
            send_y = -smooth_y if TRACKING_INVERT_Y else smooth_y
            look = LookCommand(action="look", x=round(send_x, 4), y=round(send_y, 4))
            _ = sock.sendto(look.to_json().encode(), (host, port))
            try:
                now = time.monotonic()
                if now - last_looking_at_sent >= 2.0:
                    last_looking_at_sent = now
                    ev = EyeTrackingEvent(
                        event="looking_at",
                        label=label,
                        confidence=round(conf, 2),
                        x=float(int(round(cx))),
                        y=float(int(round(cy))),
                    )
                    _ = sock.sendto(ev.to_json().encode(), ("127.0.0.1", NS_EVENTS_PORT))
            except OSError:
                pass
    except KeyboardInterrupt:
        pass
    finally:
        picam2.stop()
    print("Stopped.", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Eye tracking exited due to: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
