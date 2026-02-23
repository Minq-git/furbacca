#!/usr/bin/env bash
# Furbacca zRAM & Swap Monitor
# Shows compression ratio and SD card swap usage in real-time.
# On the Pi:  ./scripts/diagnostics/monitor-zram.sh
# From Mac:   ./scripts/diagnostics/monitor-zram.sh furbacca.local   (SSH to Pi and run there)
# SSH user:   FURBACCA_SSH_USER (default: minqz)
#
# Press Ctrl+C to stop.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Optional: first arg = host (e.g. furbacca.local) → run on Pi via SSH
if [[ -n "$1" && ( "$1" == *.* || "$1" == "furbacca" ) ]]; then
  REMOTE_HOST="$1"
  SSH_USER="${FURBACCA_SSH_USER:-minqz}"
  exec ssh -t "$SSH_USER@$REMOTE_HOST" 'cd ~/furbacca && ./scripts/diagnostics/monitor-zram.sh'
fi

cd "$REPO_DIR"

# Unbuffer stdout so the \r-updating line flushes every 2s over SSH (no "press Enter to see update")
if [[ "$1" != "__no_stdbuf__" ]] && [[ -t 1 ]] && command -v stdbuf &>/dev/null; then
  exec stdbuf -o0 "$0" "__no_stdbuf__"
fi

echo "--- Furbacca zRAM Monitor (Press Ctrl+C to stop) ---"
echo "Format: [Raw Data] -> [Compressed] (Ratio) | SD Swap | Power"
echo ""

# Convert zramctl human-readable size (e.g. 4K, 69B, 448M, 61.2K) to integer bytes
to_bytes() {
  local v="$1"
  local num="${v%%[KMG]*}"
  num="${num%%B}"
  # Strip to integer part so bash arithmetic never sees a decimal (e.g. 61.2K -> 61)
  num="${num%%.*}"
  num="${num%%[^0-9]}"
  [[ -z "$num" ]] && num=0
  local suf="${v##*[0-9]}"
  case "$suf" in
    K) echo $((num * 1024));;
    M) echo $((num * 1024 * 1024));;
    G) echo $((num * 1024 * 1024 * 1024));;
    *) echo "$num";;
  esac
}

# Prefer full path so it works when run via SSH (non-login shell may have minimal PATH)
ZRAMCTL=$(command -v zramctl 2>/dev/null || echo "/usr/sbin/zramctl")
VCGENCMD=$(command -v vcgencmd 2>/dev/null || echo "/usr/bin/vcgencmd")
while true; do
  # Get zRAM stats (DISKSIZE,DATA,COMPR — may be human-readable: 4K, 69B, 448M)
  # Capture both stdout and stderr; some zramctl write to stderr when stdout is not a TTY (e.g. over SSH)
  ZDATA=$("$ZRAMCTL" --raw --noheadings --output DISKSIZE,DATA,COMPR 2>&1 | head -1)
  # Expect at least three size-like fields (e.g. 448M 4K 69B); ignore error lines
  if [[ -z "$ZDATA" ]] || ! [[ "$ZDATA" =~ [0-9]+[KMG]?[[:space:]]+[0-9]+ ]]; then
    echo "Error: zRAM not active. Check: zramctl (or systemctl status dev-zram0.swap)" >&2
    exit 1
  fi

  DISKSIZE=$(echo "$ZDATA" | awk '{print $1}')
  RAW_DATA_HR=$(echo "$ZDATA" | awk '{print $2}')
  COMPR_DATA_HR=$(echo "$ZDATA" | awk '{print $3}')
  RAW_DATA=$(to_bytes "$RAW_DATA_HR")
  COMPR_DATA=$(to_bytes "$COMPR_DATA_HR")

  # Avoid division by zero; ratio = raw/compressed
  if [[ -n "$COMPR_DATA" && "$COMPR_DATA" -gt 0 ]]; then
    RATIO=$(awk "BEGIN { printf \"%.2f\", $RAW_DATA / $COMPR_DATA }")
  else
    RATIO="0.00"
  fi

  # SD swap used (KB) — skip header, exclude zram lines
  SD_SWAP=$(awk 'NR>1 && $1 !~ /^\/dev\/zram/ { sum += $4 } END { print sum+0 }' /proc/swaps 2>/dev/null)

  # Pi power/voltage: vcgencmd get_throttled → 0x0 = OK, non-zero = under-voltage or throttled
  THROTTLED=$("$VCGENCMD" get_throttled 2>/dev/null || echo "throttled=0x0")
  if [[ "$THROTTLED" =~ throttled=0x0 ]]; then
    POWER="POWER OK"
  else
    POWER="VOLTAGE LOW"
  fi

  # Human-readable sizes (KB)
  RAW_KB=$((RAW_DATA / 1024))
  COMPR_KB=$((COMPR_DATA / 1024))

  printf "\r\033[K"
  printf "zRAM: %s KB -> %s KB | Ratio: %s:1 | SD swap: %s KB | %s" \
         "$RAW_KB" "$COMPR_KB" "$RATIO" "${SD_SWAP:-0}" "$POWER"

  sleep 2
done
