# Eye graphics for Furbacca

**vision/eyes.py** uses textures from this folder for the animated eyes (sclera + iris + pupil). Any size is resized to 240×240.

## Assets used

| File | Use |
|------|-----|
| **iris.jpg** (or **iris.png**) | Default/human iris texture |
| **sclera.png** | Default/human sclera (white of eye) |
| **dragon-iris.jpg** | Iris for `EYE_TYPE=dragon` / `demon` |
| **dragon-sclera.png** | Sclera for `EYE_TYPE=dragon` / `demon` |
| **eye.png** / **eye.jpg** | Optional: single image for static mode (used in preference to iris) |

If no image is found, eyes fall back to the red/blue test pattern.

## Fetch eye graphics

Setup-fresh already runs this. To fetch or refresh assets (from Adafruit Pi_Eyes graphics):

```bash
./scripts/fetch-eye-graphics.sh
```

Then run **vision/eyes.py** as usual.
