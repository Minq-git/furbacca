#!/usr/bin/env python3
"""
Check how PIL Image → NumPy array maps RGB on this system.
Run on the Pi (with venv): python vision/py/check_eye_channels.py
Use the output to set EYES_NUMPY_SWAP_RB=0 or 1 so blit colors match the display.
"""
import sys
import os

# Allow running from repo root or vision/py
_vision_py = os.path.dirname(os.path.abspath(__file__))
if _vision_py not in sys.path:
    sys.path.insert(0, os.path.dirname(_vision_py))

try:
    from PIL import Image
except ImportError:
    print("PIL not found. pip install Pillow")
    sys.exit(1)
try:
    import numpy as np
except ImportError:
    print("NumPy not found. pip install numpy")
    sys.exit(1)

# Build a 3x1 image: red, green, blue (PIL RGB order)
img = Image.new("RGB", (3, 1))
img.putpixel((0, 0), (255, 0, 0))    # R
img.putpixel((1, 0), (0, 255, 0))    # G
img.putpixel((2, 0), (0, 0, 255))    # B

arr = np.array(img, dtype=np.uint8)
# arr shape: (1, 3, 3) = (height, width, channels)
r_pixel = arr[0, 0, :]   # what we got at red position
g_pixel = arr[0, 1, :]   # at green position
b_pixel = arr[0, 2, :]   # at blue position

print("PIL RGB test image → NumPy array (one row, 3 pixels):")
print("  Red   (255,0,0) →", r_pixel.tolist())
print("  Green (0,255,0) →", g_pixel.tolist())
print("  Blue  (0,0,255) →", b_pixel.tolist())

# Infer channel order: which index has 255 for R, G, B?
ch_r = int(np.argmax(r_pixel))
ch_g = int(np.argmax(g_pixel))
ch_b = int(np.argmax(b_pixel))
order = [None, None, None]
order[ch_r], order[ch_g], order[ch_b] = "R", "G", "B"
label = "".join(order)

print("")
print("Detected channel order: %s (array[:,:,0]=%s, [:,:,1]=%s, [:,:,2]=%s)" % (label, order[0], order[1], order[2]))

if label == "RGB":
    print("→ NumPy matches PIL RGB. Use EYES_NUMPY_SWAP_RB=0 (default).")
    print("  If you still get a blue tint with NumPy, the display/driver may expect different byte order.")
    print("  Use EYES_USE_NUMPY_BLIT=0 to force the fallback (correct colors, slower FPS).")
elif label == "BGR":
    print("→ NumPy is BGR (R and B swapped). Use EYES_NUMPY_SWAP_RB=1 to fix blue tint.")
else:
    print("→ Unusual order. For correct colors you may need a custom swap in blit.py.")
