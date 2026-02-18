#!/usr/bin/env bash
# Clear Matter storage so Furbacca appears uncommissioned and shows the QR code again.
# Use when you can't add or re-add Furbacca to Google Home (e.g. "already added" or link fails).
#
# Steps:
#  1. Stop Furbacca (Ctrl+C or: sudo systemctl stop furbacca)
#  2. Run from repo root: ./scripts/matter-factory-reset.sh [-y]
#  3. In Google Home app, remove Furbacca if listed (Settings → Furbacca → Remove device)
#  4. Start Furbacca (wake-furbacca) and add again with the QR code
#
# Usage: ./scripts/matter-factory-reset.sh [-y]
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_DIR"
MATTER_DIR="$REPO_DIR/.matter"
if [[ "${1:-}" != "-y" && "${1:-}" != "--yes" ]]; then
  echo "This will remove $MATTER_DIR (Matter pairing/fabric data). The device will need to be re-added."
  read -r -p "Continue? [y/N] " r
  [[ "${r,,}" == "y" || "${r,,}" == "yes" ]] || exit 0
fi
if [[ -d "$MATTER_DIR" ]]; then
  rm -rf "$MATTER_DIR"
  echo "Removed $MATTER_DIR. Restart Furbacca and add the device again (scan the new QR)."
else
  echo "No $MATTER_DIR found (already uncommissioned or storage elsewhere)."
fi
