#!/usr/bin/env bash
# Start eyes (background) and nervous system (foreground) in one terminal.
# Ctrl+C or exit stops both; eyes are blanked on exit.
# Run from repo root, or the script will cd there.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_DIR"

# Refactor check: eyes live in vision/py/ (pull latest if missing)
if [[ ! -f vision/py/eyes.py ]]; then
  echo "❌ vision/py/eyes.py not found. Pull the latest refactor: git pull"
  exit 1
fi

# If something else is on 5005 (e.g. old systemd), remote + touch won't work
if command -v ss &>/dev/null && ss -ulnp 2>/dev/null | grep -q ':5005 '; then
  echo "⚠ Port 5005 already in use. Stop other eyes first: sudo systemctl stop furbacca-eyes"
  echo "  Then run wake-furbacca again."
  exit 1
fi

EYES_PID=""
cleanup() {
  if [[ -n "$EYES_PID" ]] && kill -0 "$EYES_PID" 2>/dev/null; then
    kill "$EYES_PID" 2>/dev/null || true
    wait "$EYES_PID" 2>/dev/null || true
  fi
  python3 vision/py/blank_displays.py 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Bind 0.0.0.0 so remote (fe) and local (nervous system) commands both work
export UDP_BIND=0.0.0.0

# Start eyes in background (UDP 5005)
(
  source env/bin/activate
  python3 vision/py/eyes.py
) &
EYES_PID=$!

# Give eyes a moment to bind
sleep 1

# Nervous system in foreground (sensors, sends blink/cycle to eyes)
npm start
