#!/usr/bin/env bash
# Start eyes (background) and nervous system (foreground) in one terminal.
# Ctrl+C or exit stops both; eyes are blanked on exit.
# Run from repo root, or the script will cd there.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_DIR"

EYES_PID=""
cleanup() {
  if [[ -n "$EYES_PID" ]] && kill -0 "$EYES_PID" 2>/dev/null; then
    kill "$EYES_PID" 2>/dev/null || true
    wait "$EYES_PID" 2>/dev/null || true
  fi
  python3 vision/blank_displays.py 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Start eyes in background (UDP 5005, bind 0.0.0.0 for remote commands)
(
  source env/bin/activate
  UDP_BIND=0.0.0.0 python3 vision/eyes.py
) &
EYES_PID=$!

# Give eyes a moment to bind
sleep 1

# Nervous system in foreground (sensors, sends blink/cycle to eyes)
npm start
