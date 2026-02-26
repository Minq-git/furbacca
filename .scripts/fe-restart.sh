#!/usr/bin/env bash
# Send UDP restart_both to eyes = full hardware re-init (RST + init both panels). Same as head+belly held 5s.
# Usage: ./.scripts/fe-restart.sh [host]
#   host defaults to FURBACCA_HOST or furbacca.local (fallback VISION_HOST or 127.0.0.1).
set -e
SCRIPT_DIR_FE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR_FE="$(cd "$SCRIPT_DIR_FE/.." && pwd)"
[[ -f "$REPO_DIR_FE/.env" ]] && { set -a; source "$REPO_DIR_FE/.env"; set +a; }
HOST="${1:-${FURBACCA_HOST:-furbacca.local}}"
PORT="${VISION_PORT:-5005}"
python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.sendto(b'{\"action\":\"restart_both\"}', (\"$HOST\", $PORT))
s.close()
" 2>/dev/null || true
echo "Sent eyes restart_both to $HOST:$PORT"
