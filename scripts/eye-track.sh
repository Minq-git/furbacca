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

# On Linux, find a Python that can import picamera2 (apt installs to one version; default may differ).
# Prefer explicit versioned binaries so "run" and "on" use the same interpreter.
find_picamera2_python() {
  local py result
  if [[ -n "$FURBACCA_CAMERA_PYTHON" ]]; then
    "$FURBACCA_CAMERA_PYTHON" -c "import picamera2" 2>/dev/null && echo "$FURBACCA_CAMERA_PYTHON" && return
  fi
  for py in /usr/bin/python3.12 /usr/bin/python3.11 /usr/bin/python3.10 /usr/bin/python3; do
    [[ -x "$py" ]] && "$py" -c "import picamera2" 2>/dev/null && echo "$py" && return
  done
  py="$(command -v python3 2>/dev/null)"
  [[ -n "$py" ]] && "$py" -c "import picamera2" 2>/dev/null && echo "$py" && return
  echo ""
}

case "$ACTION" in
  on)
    if [[ "$(uname -s)" != "Linux" ]]; then
      echo "Eye tracking runs on the Pi (AI camera). From this machine, start it on the Pi:"
      echo "  $0 furbacca.local on"
      exit 0
    fi
    if pgrep -f "vision/py/camera_track.py" >/dev/null 2>&1; then
      echo "Eye tracking already running."
    else
      PYTHON3="$(find_picamera2_python)"
      if [[ -z "$PYTHON3" ]]; then
        echo "No Python with picamera2 found. Install: sudo apt install -y python3-picamera2"
        echo "If already installed, try: FURBACCA_CAMERA_PYTHON=/usr/bin/python3.12 $0 on   (or python3.11)"
        exit 1
      fi
      # Clear PYTHONPATH so reference/picamera2 or other paths don't shadow system python3-picamera2
      ( cd "$REPO_DIR" && env -u PYTHONPATH nohup "$PYTHON3" vision/py/camera_track.py >> /tmp/eye-track.log 2>&1 ) &
      PID=$!
      echo "Eye tracking starting (PID $PID). Log: /tmp/eye-track.log"
      # Give camera/model time to load; if process exits (e.g. camera not found), report it
      sleep 3
      if kill -0 "$PID" 2>/dev/null; then
        echo "Eye tracking started."
        python3 -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.sendto(b'{\"event\":\"eye_tracking_started\"}', ('127.0.0.1', 5006)); s.close()" 2>/dev/null || true
      else
        echo "Eye tracking failed to start (process exited). Last 25 lines of /tmp/eye-track.log:"
        echo "---"
        tail -n 25 /tmp/eye-track.log 2>/dev/null || echo "(log empty or missing)"
        echo "---"
        echo "Fix the error above, then run: $0 on   (or from Mac: $0 furbacca.lan on)"
        python3 -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.sendto(b'{\"event\":\"eye_tracking_stopped\"}', ('127.0.0.1', 5006)); s.close()" 2>/dev/null || true
        exit 1
      fi
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
      if [[ -f /tmp/eye-track.log ]]; then
        echo "Last 20 lines of /tmp/eye-track.log (why it stopped):"
        tail -n 20 /tmp/eye-track.log 2>/dev/null || true
      fi
    fi
    ;;
  run)
    if [[ "$(uname -s)" == "Linux" ]]; then
      PYTHON3="$(find_picamera2_python)"
      [[ -z "$PYTHON3" ]] && { echo "No Python with picamera2. Install: sudo apt install -y python3-picamera2"; exit 1; }
      # Run from repo root; clear PYTHONPATH so reference/picamera2 doesn't shadow system python3-picamera2
      cd "$REPO_DIR" && exec env -u PYTHONPATH "$PYTHON3" vision/py/camera_track.py "$@"
    else
      PYTHON3="${FURBACCA_CAMERA_PYTHON:-python3}"
      cd "$REPO_DIR" && exec env -u PYTHONPATH "$PYTHON3" vision/py/camera_track.py "$@"
    fi
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
