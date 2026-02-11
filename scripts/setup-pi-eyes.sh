#!/usr/bin/env bash
# Clone Adafruit Pi_Eyes and install Python deps so you can run their animated eyes.
# Pi_Eyes renders to the framebuffer (HDMI or fb0); to show on Furbacca's GC9A01
# displays you need a custom fbx2 (see instruction.md §4).
# Run from repo root.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PI_EYES_DIR="${REPO_DIR}/vision/pi_eyes"
GITHUB_URL="https://github.com/adafruit/Pi_Eyes/archive/refs/heads/master.zip"
ZIP_NAME="Pi_Eyes-master.zip"

echo "Furbacca: Setting up Pi_Eyes in ${PI_EYES_DIR}"

mkdir -p "$(dirname "$PI_EYES_DIR")"
cd "$REPO_DIR"

if [[ ! -f "$ZIP_NAME" ]]; then
  echo "Downloading Pi_Eyes..."
  curl -sL -o "$ZIP_NAME" "$GITHUB_URL"
fi

echo "Extracting Pi_Eyes..."
TMPDIR="${REPO_DIR}/.pi_eyes_extract"
rm -rf "$TMPDIR"
unzip -q -o "$ZIP_NAME" -d "$TMPDIR"
rm -rf "$PI_EYES_DIR"
mv "$TMPDIR/Pi_Eyes-master" "$PI_EYES_DIR"
rm -rf "$TMPDIR" "$ZIP_NAME"

# Use Furbacca's vision/graphics (eye.svg, iris.jpg, sclera.png, etc.)
if [[ -d "${REPO_DIR}/vision/graphics" ]]; then
  ln -sf ../graphics "$PI_EYES_DIR/graphics"
  echo "Linked vision/pi_eyes/graphics -> vision/graphics"
else
  echo "Warning: vision/graphics not found. Run: bash scripts/fetch-pi-eyes-graphics.sh"
fi

echo ""
echo "Pi_Eyes Python deps (install in your venv):"
echo "  pip install pi3d adafruit-blinka svg.path Pillow"
echo ""
echo "Run Pi_Eyes (renders to default display / framebuffer):"
echo "  cd vision/pi_eyes && python eyes.py"
echo ""
echo "To show animated eyes on Furbacca's GC9A01 displays you need a custom fbx2;"
echo "see instruction.md §4. Our vision/eyes.py shows animated eyes on both displays."
