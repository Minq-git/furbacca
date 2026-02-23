#!/usr/bin/env python3
"""
Furbacca eye tracking: Picamera2 + IMX500 object detection → UDP "look x y" to eyes.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import time
from typing import Any

# Synapses shared contract (UDP message shapes)
_synapses_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "synapses", "py"))
if _synapses_py not in sys.path:
    sys.path.insert(0, _synapses_py)
from vision_messages import EyeTrackingEvent, LookCommand  # noqa: E402

# Picamera2 + OpenCV are system-installed on the Pi
try:
    from picamera2 import Picamera2
    from picamera2.devices import IMX500
    from picamera2.devices.imx500 import NetworkIntrinsics
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

Detection = tuple[float, float, int, float]  # (cx, cy, class_id, confidence)
Target = tuple[float, float, float, int]  # (cx, cy, conf, cls)


def parse_detections(
    imx500: Any,
    picam2: Any,
    intrinsics: Any,
    metadata: Any,
    threshold: float = 0.5,
) -> list[Detection]:
    """Return list of (center_x, center_y, class_id, confidence) in ISP output pixel coords."""
    np_outputs = imx500.get_outputs(metadata, add_batch=True)
    if np_outputs is None:
        return []
    input_w: int
    input_h: int
    input_w, input_h = imx500.get_input_size()
    boxes: Any = np_outputs[0][0]
    scores: Any = np_outputs[1][0]
    classes: Any = np_outputs[2][0]
    if getattr(intrinsics, "bbox_normalization", False):
        boxes = boxes / input_h
    if getattr(intrinsics, "bbox_order", "yx") == "xy":
        boxes = boxes[:, [1, 0, 3, 2]]  # to y0,x0,y1,x1 for convert_inference_coords
    out: list[Detection] = []
    for box, score, cls in zip(boxes, scores, classes):
        if score < threshold:
            continue
        y0, x0, y1, x1 = box
        coords = (float(y0), float(x0), float(y1), float(x1))
        rect = imx500.convert_inference_coords(coords, metadata, picam2, stream="main")
        x, y, w, h = rect
        cx = x + w / 2
        cy = y + h / 2
        out.append((cx, cy, int(cls), float(score)))
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
    _ = ap.add_argument("--smooth", type=float, default=0.25, help="EMA smoothing 0..1 (0=no smooth, 1=no movement)")
    _ = ap.add_argument("--print-every", type=int, default=0, help="Print detections every N frames (0=off)")
    _ = ap.add_argument("--no-preview", action="store_true", default=True, help="No display (default on)")
    args = ap.parse_args()

    host: str = str(args.host)
    port: int = int(args.port)
    threshold: float = float(args.threshold)
    smooth: float = float(args.smooth)
    print_every: int = int(args.print_every)
    model_path: str = str(args.model)

    # IMX500 must be created before Picamera2
    imx500: Any = IMX500(model_path)
    intrinsics: Any = imx500.network_intrinsics
    if not intrinsics:
        intrinsics = NetworkIntrinsics()
        intrinsics.task = "object detection"
    elif intrinsics.task != "object detection":
        print("Model is not object detection.", file=sys.stderr)
        sys.exit(1)
    intrinsics.update_with_defaults()

    picam2: Any = Picamera2(imx500.camera_num)
    config: Any = picam2.create_preview_configuration(
        main={"size": (640, 480)},
        controls={"FrameRate": getattr(intrinsics, "inference_rate", 15)},
        buffer_count=6,
    )
    imx500.show_network_fw_progress_bar()
    picam2.start(config, show_preview=False)
    if getattr(intrinsics, "preserve_aspect_ratio", False):
        imx500.set_auto_aspect_ratio()

    width: int = 640
    height: int = 480
    try:
        main_config: Any = picam2.camera_configuration()
        main_size: Any = main_config.get("main", {}).get("size", (640, 480))
        if isinstance(main_size, (list, tuple)) and len(main_size) >= 2:
            width, height = int(main_size[0]), int(main_size[1])
    except Exception:
        pass

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    labels_raw: Any = getattr(intrinsics, "labels", None)
    labels: list[str] = list(labels_raw) if labels_raw else []

    smooth_x, smooth_y = 0.0, 0.0
    frame = 0
    was_looking = False
    last_looking_at_sent = 0.0  # throttle "looking_at" events to NS (~every 2s)
    print(
        f"Camera tracking → UDP {host}:{port} (smooth={smooth}, threshold={threshold})",
        file=sys.stderr,
    )
    print("Ctrl+C to stop.", file=sys.stderr)

    try:
        while True:
            metadata: Any = picam2.capture_metadata()
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

            look = LookCommand(action="look", x=round(smooth_x, 4), y=round(smooth_y, 4))
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
