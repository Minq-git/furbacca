#!/usr/bin/env bash
# Show Matter pairing code and QR URL from the furbacca service logs.
# Run on the Pi after the service has started (or use: ssh furbacca.local 'bash -s' < scripts/show-matter-pairing.sh).
# If the service isn't running, nothing will be found.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

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
  echo "No pairing info in recent logs. Device may already be commissioned, or the service just started."
  echo "Try: journalctl -u furbacca -f   and look for the QR block when Matter starts."
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
