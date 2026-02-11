#!/usr/bin/env bash
# Fetch eye assets (iris, sclera, eye.svg, etc.) from Adafruit Pi_Eyes into vision/graphics/.
# Run from repo root. Does not overwrite existing files.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GRAPHICS_DIR="${REPO_DIR}/vision/graphics"
GITHUB_URL="https://github.com/adafruit/Pi_Eyes/archive/refs/heads/master.zip"
ZIP_NAME="Pi_Eyes-master.zip"

echo "Furbacca: Fetching eye graphics into ${GRAPHICS_DIR}"

mkdir -p "$GRAPHICS_DIR"
cd "$REPO_DIR"

if [[ ! -f "$ZIP_NAME" ]]; then
  echo "Downloading Pi_Eyes (graphics only)..."
  curl -sL -o "$ZIP_NAME" "$GITHUB_URL"
fi

echo "Extracting graphics..."
TMPDIR="${REPO_DIR}/.pi_eyes_extract"
rm -rf "$TMPDIR"
unzip -q -o "$ZIP_NAME" "Pi_Eyes-master/graphics/*" -d "$TMPDIR"
cp -n "$TMPDIR"/Pi_Eyes-master/graphics/* "$GRAPHICS_DIR" 2>/dev/null || true
rm -rf "$TMPDIR" "$ZIP_NAME"

echo "Done. Contents of vision/graphics:"
ls -la "$GRAPHICS_DIR"
echo ""
echo "vision/eyes.py will use iris.jpg (or eye.png if present) on both displays."
