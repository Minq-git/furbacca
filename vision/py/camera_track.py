#!/usr/bin/env python3
"""
Furbacca eye tracking: Picamera2 + IMX500 object detection → UDP "look x y" to eyes.

Runs headless (no preview). Picks one target (prefer "person"), converts center to
normalized x,y in [-1, 1], and sends JSON {"action": "look", "x": x, "y": y} to the
eyes (UDP port 5005). Use with system Python and python3-picamera2 on the Pi.

Preferred: use the eye-track script (on/off/run). Examples:
  eye-track on                    # start in background
  eye-track run --print-every 30  # foreground, print detections
  eye-track furbacca.local on    # from Mac: start on Pi via SSH

Or run this module directly:
  python3 vision/py/camera_track.py
  python3 vision/py/camera_track.py --print-every 30 --smooth 0.2
"""

import argparse
import json
import socket
import sys
import time

# Picamera2 + OpenCV are system-installed (python3-picamera2, python3-opencv) on the Pi
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


def parse_detections(imx500, picam2, intrinsics, metadata, threshold=0.5):
    """Return list of (center_x, center_y, class_id, confidence) in ISP output pixel coords."""
    np_outputs = imx500.get_outputs(metadata, add_batch=True)
    if np_outputs is None:
        return []
    input_w, input_h = imx500.get_input_size()
    boxes = np_outputs[0][0]
    scores = np_outputs[1][0]
    classes = np_outputs[2][0]
    if getattr(intrinsics, "bbox_normalization", False):
        boxes = boxes / input_h
    if getattr(intrinsics, "bbox_order", "yx") == "xy":
        boxes = boxes[:, [1, 0, 3, 2]]  # to y0,x0,y1,x1 for convert_inference_coords
    out = []
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


def pick_target(detections, prefer_class=PERSON_CLASS_ID):
    """Choose one detection: prefer prefer_class (person), else highest confidence. Returns (cx, cy, conf, cls) or None."""
    if not detections:
        return None
    person = [d for d in detections if d[2] == prefer_class]
    if person:
        best = max(person, key=lambda d: d[3])
    else:
        best = max(detections, key=lambda d: d[3])
    return (best[0], best[1], best[3], best[2])


def center_to_normalized(cx, cy, width, height):
    """Map pixel center (cx, cy) to normalized x, y in [-1, 1]. Center of frame = (0, 0)."""
    if width <= 0 or height <= 0:
        return 0.0, 0.0
    nx = (cx / width - 0.5) * 2.0
    ny = (cy / height - 0.5) * 2.0
    return max(-1.0, min(1.0, nx)), max(-1.0, min(1.0, ny))


def main():
    ap = argparse.ArgumentParser(description="Furbacca camera tracking: IMX500 → UDP look to eyes")
    ap.add_argument("--model", default="/usr/share/imx500-models/imx500_network_ssd_mobilenetv2_fpnlite_320x320_pp.rpk", help="IMX500 model (.rpk)")
    ap.add_argument("--host", default="127.0.0.1", help="UDP host for eyes (default 127.0.0.1)")
    ap.add_argument("--port", type=int, default=UDP_PORT, help=f"UDP port (default {UDP_PORT})")
    ap.add_argument("--threshold", type=float, default=0.5, help="Detection confidence threshold")
    ap.add_argument("--smooth", type=float, default=0.25, help="EMA smoothing 0..1 (0=no smooth, 1=no movement)")
    ap.add_argument("--print-every", type=int, default=0, help="Print detections every N frames (0=off)")
    ap.add_argument("--no-preview", action="store_true", default=True, help="No display (default on)")
    args = ap.parse_args()

    # IMX500 must be created before Picamera2
    imx500 = IMX500(args.model)
    intrinsics = imx500.network_intrinsics
    if not intrinsics:
        intrinsics = NetworkIntrinsics()
        intrinsics.task = "object detection"
    elif intrinsics.task != "object detection":
        print("Model is not object detection.", file=sys.stderr)
        sys.exit(1)
    intrinsics.update_with_defaults()

    picam2 = Picamera2(imx500.camera_num)
    config = picam2.create_preview_configuration(
        main={"size": (640, 480)},
        controls={"FrameRate": getattr(intrinsics, "inference_rate", 15)},
        buffer_count=6,
    )
    imx500.show_network_fw_progress_bar()
    picam2.start(config, show_preview=False)
    if getattr(intrinsics, "preserve_aspect_ratio", False):
        imx500.set_auto_aspect_ratio()

    try:
        main_config = picam2.camera_configuration()
        main_size = main_config.get("main", {}).get("size", (640, 480))
        width, height = main_size[0], main_size[1]
    except Exception:
        width, height = 640, 480

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    labels = getattr(intrinsics, "labels", None) or []

    smooth_x, smooth_y = 0.0, 0.0
    frame = 0
    was_looking = False
    last_looking_at_sent = 0.0  # throttle "looking_at" events to NS (~every 2s)
    print(f"Camera tracking → UDP {args.host}:{args.port} (smooth={args.smooth}, threshold={args.threshold})", file=sys.stderr)
    print("Ctrl+C to stop.", file=sys.stderr)

    try:
        while True:
            metadata = picam2.capture_metadata()
            detections = parse_detections(imx500, picam2, intrinsics, metadata, threshold=args.threshold)
            frame += 1

            if args.print_every and frame % args.print_every == 0 and detections:
                for cx, cy, cls, conf in detections:
                    label = labels[cls] if cls < len(labels) else str(cls)
                    print(f"  [{frame}] {label} {conf:.2f} at ({cx:.0f}, {cy:.0f})")

            target = pick_target(detections)
            if target is None:
                if was_looking:
                    try:
                        sock.sendto(b'{"event":"looking_stopped"}', ("127.0.0.1", NS_EVENTS_PORT))
                    except OSError:
                        pass
                    was_looking = False
                continue
            cx, cy, conf, cls = target
            label = labels[cls] if cls < len(labels) else str(cls)
            nx, ny = center_to_normalized(cx, cy, width, height)

            if not was_looking:
                try:
                    sock.sendto(b'{"event":"looking_started"}', ("127.0.0.1", NS_EVENTS_PORT))
                except OSError:
                    pass
                was_looking = True

            # EMA smoothing
            alpha = 1.0 - args.smooth
            smooth_x = alpha * smooth_x + (1 - alpha) * nx
            smooth_y = alpha * smooth_y + (1 - alpha) * ny

            payload = json.dumps({"action": "look", "x": round(smooth_x, 4), "y": round(smooth_y, 4)})
            sock.sendto(payload.encode(), (args.host, args.port))
            # Notify nervous system what we're looking at (throttled: ~every 2s)
            try:
                now = time.monotonic()
                if now - last_looking_at_sent >= 2.0:
                    last_looking_at_sent = now
                    ev = json.dumps({
                        "event": "looking_at",
                        "label": label,
                        "confidence": round(conf, 2),
                        "x": int(round(cx)),
                        "y": int(round(cy)),
                    })
                    sock.sendto(ev.encode(), ("127.0.0.1", NS_EVENTS_PORT))
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
