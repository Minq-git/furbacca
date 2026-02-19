# Reference repos (not committed)

Third-party repositories kept here for **implementation reference and troubleshooting**. They are listed in `.gitignore` (e.g. `reference/picamera2`) so the main repo stays clean.

## Raspberry Pi AI Camera (Picamera2 + IMX500)

**picamera2** — Official Picamera2 with IMX500 examples (object detection, pose estimation). Useful when building the Furbacca camera process or debugging IMX500 metadata/coordinates.

```bash
# From repo root
git clone https://github.com/raspberrypi/picamera2.git reference/picamera2
```

On the Pi, install the Picamera2 system package so the demos can import it:

```bash
sudo apt install -y python3-picamera2 python3-opencv python3-munkres
```

Key paths after cloning:

- `reference/picamera2/examples/imx500/imx500_object_detection_demo.py` — object detection, `IMX500(model_file)`, `get_outputs()`, `convert_inference_coords()`
- `reference/picamera2/examples/imx500/imx500_pose_estimation_higherhrnet_demo.py` — pose estimation
- `reference/picamera2/src/picamera2/devices/imx500.py` — IMX500 helper API

**Headless (no display):** Run object detection demo with `--no-preview` to avoid “Failed to reserve DRM plane”.

See **docs/AI_CAMERA.md** for usage and eye-tracking integration.
