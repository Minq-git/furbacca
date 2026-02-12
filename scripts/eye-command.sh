#!/usr/bin/env bash
# Send a single UDP command to the eyes (e.g. change shape, blink).
# Use from another terminal while scripts/run-eyes.sh is running (eyes listen on UDP 5005).
# Usage:
#   ./scripts/eye-command.sh cycle_eye_shape
#   ./scripts/eye-command.sh set_eye_shape sharp   # or: shape sharp
#   ./scripts/eye-command.sh set_eye_type dragon    # or: type dragon
#   ./scripts/eye-command.sh blink
#   ./scripts/eye-command.sh furbacca.local shape bean   # from Mac to Pi
set -e
PORT="${EYE_UDP_PORT:-5005}"
HOST="127.0.0.1"
CMD=""
SHAPE=""

# Optional: first arg can be host (e.g. furbacca.local)
if [[ -n "$1" && "$1" == *.* ]]; then
  HOST="$1"
  shift
fi

case "$1" in
  cycle_eye_shape)
    CMD='{"action":"cycle_eye_shape"}'
    ;;
  set_eye_shape|shape)
    SHAPE="${2:-round}"
    shift
    CMD=$(printf '{"action":"set_eye_shape","shape":"%s"}' "$SHAPE")
    ;;
  blink)
    CMD='{"action":"blink"}'
    ;;
  cycle_eye_type)
    CMD='{"action":"cycle_eye_type"}'
    ;;
  set_eye_type|type)
    EYE_TYPE="${2:-default}"
    shift
    CMD=$(printf '{"action":"set_eye_type","type":"%s"}' "$EYE_TYPE")
    ;;
  nervous_look|animation)
    CMD=$(printf '{"action":"animation","name":"%s"}' "${2:-nervous_look}")
    ;;
  *)
    echo "Usage: $0 [host] <command> [arg]" >&2
    echo "  host    optional; e.g. furbacca.local (default 127.0.0.1)" >&2
    echo "  command one of: cycle_eye_shape, set_eye_shape <shape>, shape <shape>, blink, cycle_eye_type, set_eye_type <type>, type <type>, nervous_look" >&2
    echo "  shapes  round, sharp, half_moon, bean, oval, trapezoid, tilted, dome, pill" >&2
    echo "  types   default, human, dragon, demon" >&2
    echo "Examples:" >&2
    echo "  $0 cycle_eye_shape" >&2
    echo "  $0 set_eye_shape sharp    # or: $0 shape sharp" >&2
    echo "  $0 set_eye_type dragon     # or: $0 type dragon" >&2
    echo "  $0 furbacca.local shape bean" >&2
    exit 1
    ;;
esac

# Prefer Python for UDP send (reliable one-shot; macOS nc can be flaky). Fall back to nc.
if command -v python3 >/dev/null 2>&1; then
  EYE_CMD="$CMD" EYE_HOST="$HOST" EYE_PORT="$PORT" python3 -c '
import socket, os
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
msg = os.environ.get("EYE_CMD", "{}").encode()
s.sendto(msg, (os.environ["EYE_HOST"], int(os.environ["EYE_PORT"])))
'
else
  echo "$CMD" | nc -u -w1 "$HOST" "$PORT"
fi
