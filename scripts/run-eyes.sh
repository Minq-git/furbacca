#!/usr/bin/env bash
# Run vision/eyes.py and blank both displays on exit (Ctrl+C, kill, or normal exit).
# Eyes listen on UDP 5005; use scripts/eye-command.sh from another terminal to send
# commands (blink, shape sharp, cycle_eye_shape, etc.). For remote commands from e.g.
# your Mac, run with: UDP_BIND=0.0.0.0 ./scripts/run-eyes.sh
# Run from repo root. Requires venv activated or python in PATH.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_DIR"

trap 'python3 vision/blank_displays.py' EXIT

echo "Eyes starting (UDP 5005). In another terminal: $SCRIPT_DIR/eye-command.sh cycle_eye_shape  # or shape sharp, blink, etc."
exec python3 vision/eyes.py


