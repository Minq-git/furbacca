#!/usr/bin/env bash
# Run vision/py/main_eyes.py and blank both displays on exit (Ctrl+C, kill, or normal exit).
# Eyes listen on UDP 5005; use .scripts/vision/eye-command.sh from another terminal to send
# commands (blink, shape sharp, cycle_eye_shape, etc.). For remote commands from your Mac,
# set UDP_BIND=0.0.0.0 (put it inside your alias if the alias uses && so the eyes process gets it).
# Run from repo root. Requires venv activated or python in PATH.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$REPO_DIR"

trap 'python3 -m vision.py.blank_displays' EXIT

# Bind 0.0.0.0 so remote commands (e.g. fe from Mac) work; override with UDP_BIND=127.0.0.1 for local-only
export UDP_BIND="${UDP_BIND:-0.0.0.0}"
echo "Eyes starting (UDP 5005, bind $UDP_BIND). In another terminal: $SCRIPT_DIR/eye-command.sh cycle_eye_shape  # or shape sharp, blink, etc."
exec python3 -m vision.py.main_eyes


