#!/usr/bin/env bash
# Send a single UDP command to the eyes (e.g. change shape, blink).
# Use from another terminal while .scripts/vision/run-eyes.sh is running (eyes listen on UDP 5005).
# Usage:
#   ./.scripts/vision/eye-command.sh anim nervous_look
#   ./.scripts/vision/eye-command.sh anim shiver
#   ./.scripts/vision/eye-command.sh blink
#   ./.scripts/vision/eye-command.sh shape sharp
#   ./.scripts/vision/eye-command.sh type dragon
#   ./.scripts/vision/eye-command.sh furbacca.local anim shiver   # from Mac (fe anim shiver)
set -e
SCRIPT_DIR_EC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR_EC="$(cd "$SCRIPT_DIR_EC/../.." && pwd)"
[[ -f "$REPO_DIR_EC/.env" ]] && { set -a; source "$REPO_DIR_EC/.env"; set +a; }
PORT="${VISION_PORT:-5005}"
HOST="${VISION_HOST:-127.0.0.1}"
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
  anim)
    ANIM_NAME="${2:-nervous_look}"
    shift
    CMD=$(printf '{"action":"animation","name":"%s"}' "$ANIM_NAME")
    ;;
  nervous_look)
    CMD='{"action":"animation","name":"nervous_look"}'
    ;;
  shiver|impulse)
    CMD='{"action":"animation","name":"shiver"}'
    ;;
  *)
    echo "Usage: $0 [host] <command> [arg]" >&2
    echo "  host    optional; e.g. furbacca.local (default from VISION_HOST or 127.0.0.1)" >&2
    echo "  command one of: cycle_eye_shape, shape <shape>, blink, cycle_eye_type, type <type>, anim <name>, nervous_look, shiver" >&2
    echo "  anim    anim <name> — nervous_look, shiver (or use nervous_look / shiver directly)" >&2
    echo "  shapes  round, sharp, half_moon, bean, oval, tilted, dome, pill, anime, concern, glare, gemini, heart, kawaii, stern, sus" >&2
    echo "  types   default, human, dragon, demon" >&2
    echo "Examples:" >&2
    echo "  $0 anim nervous_look" >&2
    echo "  $0 anim shiver" >&2
    echo "  $0 blink" >&2
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
