#!/usr/bin/env bash
# Start eyes (vision/py/eyes.py) + nervous system. One terminal; Ctrl+C stops both.
# Run from repo root, or the script will cd there. Sync from Mac (push-furbacca) if you see "vision/eyes.py: No such file".

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_DIR"

# Refactor check: eyes live in vision/py/ (pull latest if missing)
if [[ ! -f vision/py/eyes.py ]]; then
  echo "❌ vision/py/eyes.py not found. Sync from your Mac: push-furbacca"
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
  # Close eyelids before shutting down (graceful shutdown)
  if command -v python3 >/dev/null 2>&1; then
    EYE_CMD='{"action":"eyes_close"}' EYE_HOST="${EYE_UDP_HOST:-127.0.0.1}" EYE_PORT="${EYE_UDP_PORT:-5005}" python3 -c '
import socket, os
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.sendto(os.environ.get("EYE_CMD", "{}").encode(), (os.environ["EYE_HOST"], int(os.environ["EYE_PORT"])))
' 2>/dev/null || true
    sleep 0.25
  fi
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

echo "Initializing nervous system..."
# Nervous system in foreground (sensors, sends blink/cycle to eyes)
npm start
