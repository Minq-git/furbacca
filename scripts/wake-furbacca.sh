#!/usr/bin/env bash
# Start eyes (vision/py/main_eyes.py) + nervous system. One terminal; Ctrl+C stops both.
# Eye-tracking (camera/camera_track.py) starts by default on the Pi; use --no-eye-track or FURBACCA_EYE_TRACK=0 to disable.
# Run from repo root, or the script will cd there. Sync from Mac (push-furbacca) if you see "vision/py/main_eyes.py: No such file".

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Option: disable eye-tracking (AI camera → eyes follow)
while [[ -n "$1" ]]; do
  case "$1" in
    --no-eye-track|-n) export FURBACCA_EYE_TRACK=0; shift ;;
    *) break ;;
  esac
done

cd "$REPO_DIR"

# Refactor check: eyes live in vision/py/ (pull latest if missing)
if [[ ! -f vision/py/main_eyes.py ]]; then
  echo "❌ vision/py/main_eyes.py not found. Sync from your Mac: push-furbacca"
  exit 1
fi

# If something else is on 5005 (e.g. old systemd), remote + touch won't work
if command -v ss &>/dev/null && ss -ulnp 2>/dev/null | grep -q ':5005 '; then
  echo "⚠ Port 5005 already in use. Stop other eyes first: sudo systemctl stop furbacca-eyes"
  echo "  Then run wake-furbacca again."
  exit 1
fi

EYE_TRACK_STARTED_BY_US=0

cleanup() {
  # Stop eye-tracking if we started it (so Ctrl+C leaves eye-track off when started with --no-eye-track next time)
  if [[ "$EYE_TRACK_STARTED_BY_US" -eq 1 ]]; then
    "$REPO_DIR/scripts/vision/eye-track.sh" off 2>/dev/null || true
  fi
  # Close eyelids and blank displays on exit (nervous system kills eyes process; this helps if eyes still respond)
  if command -v python3 >/dev/null 2>&1; then
    EYE_CMD='{"action":"eyes_close"}' EYE_HOST="${EYE_UDP_HOST:-127.0.0.1}" EYE_PORT="${EYE_UDP_PORT:-5005}" python3 -c '
import socket, os
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.sendto(os.environ.get("EYE_CMD", "{}").encode(), (os.environ["EYE_HOST"], int(os.environ["EYE_PORT"])))
' 2>/dev/null || true
    sleep 0.25
  fi
  python3 vision/py/blank_displays.py 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Bind 0.0.0.0 so remote (fe) and local (nervous system) commands both work
export UDP_BIND=0.0.0.0

# Build first. On Pi, use build:pi so tsc doesn't OOM. Then sync voice so dist/voice/assets/ has WAVs (giggle, etc.).
echo "Building nervous system..."
if [[ "$(uname -s)" == "Linux" ]]; then
  npm run build:pi
else
  npm run build
fi
npm run sync-sounds
# Self-heal: if audio module missing (e.g. stale incremental build), clean build once
if [[ ! -f dist/voice/ts/audio.js ]]; then
  echo "Missing dist/voice/ts/audio.js, doing clean build..."
  rm -rf dist
  if [[ "$(uname -s)" == "Linux" ]]; then
    npm run build:pi
  else
    npm run build
  fi
  npm run sync-sounds
fi

# On Pi (low RAM), limit Node heap for the runtime process
[[ "$(uname -s)" == "Linux" ]] && export NODE_OPTIONS=--max-old-space-size=384

# Start eye-tracking by default on the Pi (AI camera → eyes follow). Disable with --no-eye-track or FURBACCA_EYE_TRACK=0
if [[ "$(uname -s)" == "Linux" && "${FURBACCA_EYE_TRACK:-1}" != "0" ]]; then
  if [[ -f vision/py/camera/camera_track.py ]]; then
    if ! pgrep -f "vision/py/camera/camera_track.py" >/dev/null 2>&1; then
      if "$REPO_DIR/scripts/vision/eye-track.sh" on; then
        EYE_TRACK_STARTED_BY_US=1
      fi
    fi
  fi
fi

# Nervous system spawns eyes and restarts them if they crash (e.g. during Matter init)
echo "Starting nervous system (eyes managed by Node)..."
node dist/nervous_system.js
