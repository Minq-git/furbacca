#!/usr/bin/env bash
# Fresh setup: venv, pip deps, gc9a01py driver, eye graphics.
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

# 2. Activate and pip install (vision/py/eyes.py deps)
echo "Installing pip packages..."
# shellcheck source=/dev/null
source env/bin/activate
pip install --quiet --upgrade pip
pip install --quiet spidev RPi.GPIO Pillow numpy

# 3. Fetch gc9a01py driver (required for vision/py/eyes.py)
echo "Fetching gc9a01py driver..."
bash scripts/setup/fetch-gc9a01py.sh

# 4. Fetch eye graphics (iris.jpg, eye.svg, sclera.png, etc. into vision/py/graphics)
echo "Fetching eye graphics..."
bash scripts/setup/fetch-eye-graphics.sh

echo ""
echo "=== Setup complete ==="
echo "Activate venv and run eyes:"
echo "  source env/bin/activate"
echo "  python vision/py/eyes.py"
echo ""
echo "SPI config: instruction.md (§3.1)"
