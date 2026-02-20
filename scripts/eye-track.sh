#!/usr/bin/env bash
# Start, stop, or run the eye-tracking process (vision/py/camera_track.py) on the Pi.
# Same host pattern as fe-restart / eye-command: optional host first, then on|off|status|run [args...].
#
# Usage:
#   On Pi:   ./scripts/eye-track.sh on | off | status
#   On Pi:   ./scripts/eye-track.sh run [--print-every 30 ...]   # foreground, pass args to camera_track.py
#   From Mac: ./scripts/eye-track.sh furbacca.local on | off | status
#
# SSH user: FURBACCA_SSH_USER (default: minqz)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Optional: first arg = host → run on Pi via SSH
if [[ -n "$1" && ( "$1" == *.* || "$1" == "furbacca" ) ]]; then
  REMOTE_HOST="$1"
  shift
  SSH_USER="${FURBACCA_SSH_USER:-minqz}"
  exec ssh "$SSH_USER@$REMOTE_HOST" "cd ~/furbacca && ./scripts/eye-track.sh $*"
fi

ACTION="${1:-status}"
shift || true

case "$ACTION" in
  on)
    if pgrep -f "vision/py/camera_track.py" >/dev/null 2>&1; then
      echo "Eye tracking already running."
    else
      nohup python3 "$REPO_DIR/vision/py/camera_track.py" >> /tmp/eye-track.log 2>&1 &
      echo "Eye tracking started (PID $!). Log: /tmp/eye-track.log"
      python3 -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.sendto(b'{\"event\":\"eye_tracking_started\"}', ('127.0.0.1', 5006)); s.close()" 2>/dev/null || true
    fi
    ;;
  off)
    if pkill -f "vision/py/camera_track.py" 2>/dev/null; then
      echo "Eye tracking stopped."
      python3 -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.sendto(b'{\"event\":\"eye_tracking_stopped\"}', ('127.0.0.1', 5006)); s.close()" 2>/dev/null || true
    else
      echo "Eye tracking was not running."
    fi
    ;;
  status)
    if pgrep -f "vision/py/camera_track.py" >/dev/null 2>&1; then
      echo "Eye tracking: running"
      pgrep -af "vision/py/camera_track.py" 2>/dev/null || true
    else
      echo "Eye tracking: stopped"
    fi
    ;;
  run)
    exec python3 "$REPO_DIR/vision/py/camera_track.py" "$@"
    ;;
  *)
    echo "Usage: $0 [host] <on|off|status|run [args...]>" >&2
    echo "  host   optional; e.g. furbacca.local (run on Pi via SSH)" >&2
    echo "  on     start eye tracking in background (eyes follow detected person/target)" >&2
    echo "  off    stop eye tracking" >&2
    echo "  status show if eye tracking is running" >&2
    echo "  run    run eye tracking in foreground; pass args to camera_track.py (e.g. --print-every 30)" >&2
    echo "Examples:" >&2
    echo "  $0 on" >&2
    echo "  $0 run --print-every 30" >&2
    echo "  $0 furbacca.local on" >&2
    echo "  $0 furbacca.local off" >&2
    exit 1
    ;;
esac
