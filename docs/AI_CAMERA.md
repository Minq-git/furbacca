# Raspberry Pi AI Camera (IMX500) — Furbacca integration

This doc summarizes the [Raspberry Pi AI Camera documentation](https://www.raspberrypi.com/documentation/accessories/ai-camera.html): what we use to run and deploy models, existing models/apps, **how to make Furbacca’s eyes track you**, and **headless verification** (no display — GC9A01 eyes only). See **README.md** for TODOs: AI camera process, IR transmitter, **Matter camera endpoint** (live feed via Google Home), and **build & train custom model** (AITRIOS tutorial).

---

## 1. What we leverage

### 1.1 Stack (no CPU inference)

- **IMX500 sensor** (Sony): On-sensor AI. The camera has a small ISP that turns raw frames into an **input tensor** and runs a neural network **on the camera**. The Pi receives **output tensors** (e.g. boxes, scores, poses) and optionally the normal image stream. No need for an external accelerator or heavy CPU inference on the Pi.
- **libcamera** exposes inference via controls: `CnnOutputTensor`, `CnnInputTensor`, `CnnOutputTensorInfo`, `CnnInputTensorInfo`.
- **rpicam-apps** and **Picamera2** both have IMX500 post-processing stages and helpers to parse tensors and convert coordinates to image space.

### 1.2 Firmware and models (from `imx500-all`)

- **Firmware:** `/lib/firmware/imx500_loader.fpk`, `/lib/firmware/imx500_firmware.fpk` (loaded by the kernel when the camera starts; first run can take a few minutes).
- **Pre-packaged model firmware:** `/usr/share/imx500-models/` (e.g. MobileNet SSD, PoseNet). These are `.rpk` files loaded at runtime onto the IMX500.
- **Post-processing configs:** `/usr/share/rpi-camera-assets/` — e.g. `imx500_mobilenet_ssd.json`, `imx500_posenet.json` for object detection and pose estimation.

### 1.3 Existing apps we can use

| App / API | Use |
|-----------|-----|
| **rpicam-hello** | Live viewfinder with object detection or pose overlay; good for quick tests. |
| **rpicam-vid** | Record video with detection overlays. |
| **Picamera2** (Python) | Full control in Python: start camera, get frames + metadata, read `imx500.get_outputs(metadata)` for boxes/scores/classes or pose keypoints. Best fit for a **Furbacca camera process** that streams results (e.g. UDP) to the nervous system. |
| **rpicam-apps** (C++) | Same pipeline in C++; use `IMX500PostProcessingStage` and metadata (e.g. `object_detect.results`) for custom stages. |

**Picamera2 deps (for Python demos / our process):**

```bash
sudo apt install -y python3-picamera2 python3-opencv python3-munkres
```

On the Pi, **python3-picamera2** is required so `import picamera2` works. Run demos with system Python (not inside Furbacca’s venv) unless you install picamera2 into the venv.

Examples live in the [picamera2 repo](https://github.com/raspberrypi/picamera2), under `examples/imx500/`.

**Local reference (recommended for implementation and troubleshooting):** Clone picamera2 into the project so we can read the demo code when building the Furbacca camera process or debugging. The clone is gitignored; only the convention is tracked.

```bash
# From Furbacca repo root (on Mac or Pi)
git clone https://github.com/raspberrypi/picamera2.git reference/picamera2
```

See **reference/README.md** for paths (e.g. `reference/picamera2/examples/imx500/imx500_object_detection_demo.py`, `reference/picamera2/src/picamera2/devices/imx500.py`).

---

## 2. Build and deploy custom models

To run **your own** network on the IMX500:

1. **Model:** Create or reuse a floating-point model (PyTorch or TensorFlow). Follow the [AITRIOS Raspberry Pi AI Camera tutorial](https://developer.aitrios.sony-semicon.com/en/docs/raspberry-pi-ai-camera/raspberry-pi-ai-camera-tutorial?version=2025-09-30) for build & train steps.
2. **Quantize/compress:** Use **Edge-MDT** (Model Development Toolkit), e.g. `pip install edge-mdt[pt]`. Sony’s Model Compression Toolkit (MCT) produces quantized Keras or ONNX.
3. **Convert to IMX500 binary:** Run the converter (installed with Edge-MDT), e.g.  
   `imxconv-pt -i <compressed ONNX> -o <output folder>`  
   Use `--no-input-persistency` for best memory use (disables input tensor for debugging). Output: `packerOut.zip`.
4. **Package on the Pi:** Install `imx500-tools` on the Pi, then:  
   `imx500-package -i <path to packerOut.zip> -o <output folder>`  
   This produces `network.rpk`. Pass that path to Picamera2/rpicam-apps (e.g. `IMX500(model_file)` or post-process JSON `network_file`).

So: **build/convert on a powerful machine; package RPK on the Pi.** Pre-built models in `/usr/share/imx500-models/` are enough for face/object/pose and eye tracking without custom training.

---

## 3. Using existing models for Furbacca

### 3.1 Object detection (e.g. “person” or face)

- **Model:** MobileNet SSD (pre-packaged). Config: `/usr/share/rpi-camera-assets/imx500_mobilenet_ssd.json`.
- **rpicam-hello (quick test):**
  ```bash
  rpicam-hello -t 0s --post-process-file /usr/share/rpi-camera-assets/imx500_mobilenet_ssd.json --viewfinder-width 1920 --viewfinder-height 1080 --framerate 30
  ```
- **Picamera2:** The demo script lives in the picamera2 repo. Clone it, install deps, then run from the repo root:
  ```bash
  git clone https://github.com/raspberrypi/picamera2.git ~/picamera2
  cd ~/picamera2
  sudo apt install -y python3-opencv python3-munkres   # if not already
  python examples/imx500/imx500_object_detection_demo.py --model /usr/share/imx500-models/imx500_network_ssd_mobilenetv2_fpnlite_320x320_pp.rpk
  ```
  **Headless (no display / GC9A01 eyes only):** Add **`--no-preview`** so the demo doesn’t try to use DRM and crash with “Failed to reserve DRM plane”:
  ```bash
  python examples/imx500/imx500_object_detection_demo.py --model /usr/share/imx500-models/imx500_network_ssd_mobilenetv2_fpnlite_320x320_pp.rpk --no-preview
  ```
  (Picamera2 is usually installed system-wide on Pi; if the script fails with import errors, install with `sudo apt install -y python3-picamera2` or use the repo’s Python path.)
- **Output:** Bounding boxes + confidence. Filter by class (e.g. “person”) and take the largest or highest-confidence box as “target” for tracking.

### 3.2 Pose estimation (body / face region)

- **Model:** PoseNet or HigherHRNet (pre-packaged). Config: `/usr/share/rpi-camera-assets/imx500_posenet.json`.
- **rpicam-hello:**
  ```bash
  rpicam-hello -t 0s --post-process-file /usr/share/rpi-camera-assets/imx500_posenet.json --viewfinder-width 1920 --viewfinder-height 1080 --framerate 30
  ```
- **Picamera2:** e.g. `imx500_pose_estimation_higherhrnet_demo.py`.
- **Output:** Keypoints (e.g. nose, eyes, shoulders). Use a central point (e.g. nose or mid-torso) as the tracking target.

---

## 4. Making Furbacca’s eyes track you

### 4.1 Goal

- **Input:** AI camera (IMX500) — object detection or pose estimation.
- **Output:** Eye “look” target in the same format the eyes already use: **UDP `look` with `x`, `y` in the range **-1..1** (e.g. from **vision/ts/eye_bridge.ts** / eye commands). So we need to turn **camera-space detections** into **normalized x, y** and send them to the eyes.

### 4.2 Pipeline

1. **Camera process (Python, Picamera2)**  
   - Start camera with an IMX500 model (object detection or pose).  
   - Each frame: read metadata, get outputs via `imx500.get_outputs(metadata)`.  
   - Pick one “target” (e.g. largest person box, or pose center).  
   - Convert target from **image coordinates** to **normalized x, y** in [-1, 1] (e.g. center of frame = 0,0; left = -1, right = +1).  
   - Optionally smooth (e.g. exponential moving average) to avoid jitter.  
   - Send to the nervous system or directly to the eyes.

2. **Streaming results**  
   - **Option A — UDP to eyes:** Camera process sends UDP messages to the same host:port the eyes use (e.g. `localhost:5005`), with the same `look` payload format (e.g. `look x y` or whatever **vision/py/eyes.py** expects). Then eyes track without the nervous system.  
   - **Option B — Nervous system:** Camera process sends detections to the nervous system (e.g. UDP or pipe); nervous system calls the existing eye bridge to send `look` (and optionally blink). Keeps all “behavior” in one place.

3. **Coordinate conversion**  
   - Picamera2/IMX500: use `imx500.convert_inference_coords(coords, metadata, picam2)` to get boxes/keypoints in **ISP output image space**.  
   - Then map that image space to normalized **x, y**:  
     - `x = (center_x / width - 0.5) * 2`  → range about [-1, 1].  
     - `y = (center_y / height - 0.5) * 2` (or negate if you want “person up” = positive y).  
   - Furbacca’s eyes already accept `look x y` in -1..1; no change needed on the eye side if we send that.

### 4.3 Practical steps (after headless verification)

1. **Verify camera headless:** See **§5** below. Once a still (and optionally a detection still) works, the camera and IMX500 pipeline are OK.  
2. **Eye tracking:** **scripts/eye-track.sh** (alias **eye-track**) — starts **vision/py/camera_track.py** (Picamera2 + IMX500). From Mac: **`eye-track furbacca.local on`** (or `off`, `status`). On the Pi:
   **`eye-track on`** or **`eye-track run --print-every 30`**. Options: **`--host`**, **`--port`** (5005), **`--threshold`** (0.5), **`--smooth`** (EMA 0..1), **`--print-every N`**.  
3. **Start order:** Run **wake-furbacca** (eyes + nervous system), then **eye-track on** (or `eye-track run` in another terminal). The eyes will follow the chosen target (person if present, else highest-confidence detection).  
4. **Tune:** Use **`--smooth`** (e.g. 0.2–0.3) to reduce jitter; **`--threshold`** to ignore low-confidence detections.

### 4.4 References

- [Raspberry Pi AI Camera](https://www.raspberrypi.com/documentation/accessories/ai-camera.html) — getting started, examples, under the hood.  
- [Picamera2 IMX500 examples](https://github.com/raspberrypi/picamera2/blob/main/examples/imx500/) — object detection and pose demos.  
- Furbacca eyes UDP: **vision/ts/eye_bridge.ts**, **vision/py/eyes.py** (e.g. `look` with `x`, `y` in -1..1).  
- **instruction.md** §1 — AI Camera (CSI), pinout; **README.md** — TODO (AI camera process, eye tracking, Matter camera endpoint, AITRIOS build & train).

---

## 5. Headless verification (no display — GC9A01 eyes only)

These steps confirm the AI camera and IMX500 pipeline work **without an HDMI monitor**. All output goes to files or stdout; you can inspect files later (e.g. `scp` to your Mac).

### 5.1 Prerequisites

- **imx500-all** installed (`sudo apt install imx500-all`) and **reboot** done at least once so the kernel can load firmware.
- AI camera connected via CSI (ribbon). No display required.

### 5.2 Step 1 — Check the camera is detected

From SSH (or serial):

```bash
rpicam-hello --list-cameras
```

You should see the IMX500 (e.g. “imx500” or “Raspberry Pi AI Camera”). On some systems `libcamera-hello` is not installed; the rpicam-apps tools (`rpicam-still`, `rpicam-hello`) are sufficient. If listing fails or tries to open a window headless, skip to Step 2 — if the still captures, the camera is detected.

### 5.3 Step 2 — Capture a plain still (no AI)

Writes a JPEG to a file; no display, no post-processing.

```bash
rpicam-still -o /tmp/camera-test.jpg -n
```

- **-n** = no preview window (required when headless).  
- If it runs and exits without error, the camera and basic pipeline work.  
- View the image from your Mac (include the destination, e.g. current directory):  
  `scp minqz@furbacca.local:/tmp/camera-test.jpg .`

### 5.4 Step 3 — Capture a still with object detection (IMX500)

This loads the IMX500 firmware and MobileNet SSD and writes a JPEG with bounding boxes drawn. **First run can take several minutes** while firmware loads (progress may appear on the console).

```bash
rpicam-still -o /tmp/camera-detection.jpg -n \
  --post-process-file /usr/share/rpi-camera-assets/imx500_mobilenet_ssd.json
```

- If the JSON path differs on your system, look under `/usr/share/rpi-camera-assets/` or `/usr/share/imx500-models/`.  
- When it finishes, copy the file from your Mac:  
  `scp minqz@furbacca.local:/tmp/camera-detection.jpg .`  
  Then open the image; you should see boxes around detected objects (person, etc.).  
- Later runs will be much faster (firmware cached).

### 5.5 Step 4 — Optional: short video to file

Confirms the video + detection pipeline (still no display):

```bash
rpicam-vid -t 5000 -o /tmp/camera-test.264 -n \
  --post-process-file /usr/share/rpi-camera-assets/imx500_mobilenet_ssd.json
```

- **-t 5000** = 5 seconds.  
- Playback on Mac: e.g. `ffplay` or VLC; or convert with `ffmpeg` if needed.

### 5.6 Step 5 — See what the camera saw (print detections)

The picamera2 object detection demo with `--no-preview` doesn't show output. To see what it's detecting:

- **Save a still with boxes** (Step 3): copy the image to your Mac and open it.  
- **Eye tracking:** Run **`eye-track run --print-every 30`** (or `./scripts/eye-track.sh run --print-every 30`) to print detections every N frames (e.g. person 0.92 at 320,240). (e.g. “detections: 2, person 0.95 at …”) and exit after a few seconds.

See **§4.3** and the script's `--help` for options.

### 5.7 Troubleshooting (headless)

- **“No camera detected”:** Check CSI ribbon (contacts toward the right pins), reboot, run `rpicam-hello --list-cameras` again.  
- **First detection run very slow:** Normal; IMX500 firmware load. Wait for completion; next runs are faster.  
- **rpicam-still fails with “preview” or “display” errors:** Add **-n** (no preview).  
- **Permission or “resource busy”:** Ensure no other process is using the camera (e.g. another rpicam-* or Python script).
