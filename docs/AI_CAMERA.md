# Raspberry Pi AI Camera (IMX500) — Furbacca integration

This doc summarizes the [Raspberry Pi AI Camera documentation](https://www.raspberrypi.com/documentation/accessories/ai-camera.html): what we use to run and deploy models, existing models/apps, and **how to make Furbacca’s eyes track you**.

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
sudo apt install python3-opencv python3-munkres
```

Examples live in the [picamera2 repo](https://github.com/raspberrypi/picamera2), under `examples/imx500/`.

---

## 2. Build and deploy custom models

To run **your own** network on the IMX500:

1. **Model:** Create or reuse a floating-point model (PyTorch or TensorFlow). See [AITRIOS](https://developer.aitrios.sony-semicon.com/en/raspberrypi-ai-camera).
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
- **Picamera2:** Use `examples/imx500/imx500_object_detection_demo.py` with a model from `/usr/share/imx500-models/`, e.g.:
  ```bash
  python imx500_object_detection_demo.py --model /usr/share/imx500-models/imx500_network_ssd_mobilenetv2_fpnlite_320x320_pp.rpk
  ```
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

### 4.3 Practical steps

1. **Verify camera:** After `imx500-all` and reboot, run `rpicam-hello` or a Picamera2 IMX500 demo to confirm detection/pose.  
2. **Add a small Python camera process** (e.g. under `vision/py/` or a new `camera/` dir) using Picamera2 + IMX500, and in the request callback: parse outputs → pick target → convert to x, y → send UDP (e.g. `look <x> <y>` to port 5005).  
3. **Start the camera process** with wake-furbacca (or as a separate service) so it runs alongside the eyes and nervous system.  
4. **Tune:** Use temporal filtering (e.g. in the JSON config or in our code) to reduce jitter; optionally only send `look` when confidence is above a threshold.

### 4.4 References

- [Raspberry Pi AI Camera](https://www.raspberrypi.com/documentation/accessories/ai-camera.html) — getting started, examples, under the hood.  
- [Picamera2 IMX500 examples](https://github.com/raspberrypi/picamera2/blob/main/examples/imx500/) — object detection and pose demos.  
- Furbacca eyes UDP: **vision/ts/eye_bridge.ts**, **vision/py/eyes.py** (e.g. `look` with `x`, `y` in -1..1).  
- **instruction.md** §1 — AI Camera (CSI), pinout; **README.md** — TODO (AI camera process, eye tracking).
