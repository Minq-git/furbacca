#!/usr/bin/env bash
# Show Matter pairing code and QR URL from the furbacca service logs.
# On the Pi: ./.scripts/matter/show-matter-pairing.sh
# From Mac:  ./.scripts/matter/show-matter-pairing.sh furbacca.local   (SSH to Pi and run there)
# SSH user:  FURBACCA_SSH_USER (default: minqz)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Optional: first arg = host (e.g. furbacca.local) → run on Pi via SSH
if [[ -n "$1" && ( "$1" == *.* || "$1" == "furbacca" ) ]]; then
  REMOTE_HOST="$1"
  SSH_USER="${FURBACCA_SSH_USER:-minqz}"
  exec ssh "$SSH_USER@$REMOTE_HOST" 'cd ~/furbacca && ./.scripts/matter/show-matter-pairing.sh'
fi

cd "$REPO_DIR"

echo "=== Matter pairing info (from furbacca service logs) ==="
echo ""

LOG=$(journalctl -u furbacca -n 1500 -o cat 2>/dev/null || true)
if [[ -z "$LOG" ]]; then
  echo "No furbacca service logs found. Is the service running? (sudo systemctl status furbacca)"
  exit 1
fi

# Extract key lines (most recent occurrence of each type)
PASSCODE=$(echo "$LOG" | grep -E "passcode: [0-9]+" | tail -1)
DISC=$(echo "$LOG" | grep -E "discriminator: [0-9]+" | tail -1)
MANUAL=$(echo "$LOG" | grep -E "manual pairing code: [0-9]+" | tail -1)
QRURL=$(echo "$LOG" | grep -E "QR code URL: https://" | tail -1)

if [[ -z "$PASSCODE" && -z "$MANUAL" && -z "$QRURL" ]]; then
  echo "No pairing info in recent logs (device may already be commissioned — we don't reprint QR then)."
  echo "Using Furbacca's fixed credentials (same for initial or multi-admin add):"
  echo ""
  echo "  passcode: 20202021"
  echo "  discriminator: 3840"
  echo "  manual pairing code: 34970112332"
  echo "  QR code URL: https://project-chip.github.io/connectedhomeip/qrcode.html?data=MT:Y.K90AFN00KA0648G00"
  echo ""
  echo "Add device via Matter and enter the manual code above, or open the URL to scan the QR."
  exit 0
fi

[[ -n "$PASSCODE" ]] && echo "$PASSCODE"
[[ -n "$DISC" ]] && echo "$DISC"
[[ -n "$MANUAL" ]] && echo "$MANUAL"
[[ -n "$QRURL" ]] && echo "$QRURL"

if [[ -n "$QRURL" ]]; then
  echo ""
  echo "Open the URL above in a phone/browser to get the QR code for pairing."
fi

# Optionally reprint the ASCII QR block if present (last occurrence)
QR_BLOCK=$(echo "$LOG" | awk '/▄▄▄▄▄▄▄▄▄▄/{found=1} found{print; if(/▀▀▀▀▀▀▀▀▀▀/){exit}}' | tail -15)
if [[ -n "$QR_BLOCK" ]]; then
  echo ""
  echo "ASCII QR (scan with phone camera or use URL above):"
  echo "$QR_BLOCK"
fi
