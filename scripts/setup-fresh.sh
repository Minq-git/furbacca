#!/usr/bin/env bash
# Fresh setup: venv, pip deps, gc9a01py driver, Pi_Eyes graphics.
# Run from repo root. Idempotent (safe to run again).

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_DIR"

echo "=== Furbacca fresh setup (from $REPO_DIR) ==="

# 1. Python venv
if [[ ! -d env ]]; then
  echo "Creating venv..."
  python3 -m venv env
else
  echo "Venv already exists."
fi

# 2. Activate and pip install (vision + Pi_Eyes deps)
echo "Installing pip packages..."
# shellcheck source=/dev/null
source env/bin/activate
pip install --quiet --upgrade pip
pip install --quiet spidev RPi.GPIO Pillow
# Pi_Eyes animated eyes (pi3d, adafruit-blinka, svg.path)
pip install --quiet pi3d adafruit-blinka svg.path

# 3. Fetch gc9a01py driver (required for vision/eyes.py)
echo "Fetching gc9a01py driver..."
bash scripts/fetch-gc9a01py.sh

# 4. Fetch Pi_Eyes graphics (eye.svg, iris.jpg, sclera.png, etc.)
echo "Fetching Pi_Eyes graphics..."
bash scripts/fetch-pi-eyes-graphics.sh

# 5. Set up Pi_Eyes repo (vision/pi_eyes) for animated eyes on HDMI/fb
echo "Setting up Pi_Eyes..."
bash scripts/setup-pi-eyes.sh

echo ""
echo "=== Setup complete ==="
echo "Activate venv and run eyes:"
echo "  source env/bin/activate"
echo "  python vision/eyes.py"
echo ""
echo "Pi_Eyes animated eyes (HDMI/fb): cd vision/pi_eyes && python eyes.py"
echo "SPI config: instruction.md (§3.1)"
