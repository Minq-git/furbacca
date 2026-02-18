#!/usr/bin/env bash
# Clear Matter storage so Furbacca appears uncommissioned and shows the QR code again.
# Use this when you can't add or re-add Furbacca to Google Home (e.g. "already added" or link fails).
#
# Steps:
#  1. Stop Furbacca (Ctrl+C or: sudo systemctl stop furbacca)
#  2. Run this script from repo root: ./scripts/matter-factory-reset.sh
#  3. In the Google Home app, remove Furbacca if it's listed (Settings → Furbacca → Remove device)
#  4. Start Furbacca (wake-furbacca) and add it again with the QR code

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MATTER_DIR="$REPO_DIR/.matter"

cd "$REPO_DIR"

if [[ ! -d "$MATTER_DIR" ]]; then
  echo "No .matter directory found. Furbacca will show the QR code on next start."
  exit 0
fi

if [[ "${1:-}" != "-y" && "${1:-}" != "--yes" ]]; then
  echo "This will remove Matter pairing data so Furbacca can be added to Google Home again."
  echo "Directory to remove: $MATTER_DIR"
  echo ""
  read -r -p "Continue? [y/N] " reply
  if [[ "${reply^^}" != "Y" && "${reply^^}" != "YES" ]]; then
    echo "Cancelled."
    exit 0
  fi
fi

echo "Removing $MATTER_DIR ..."
rm -rf "$MATTER_DIR"
echo "Done. Start Furbacca (wake-furbacca), then in Google Home: remove the old Furbacca device if listed, and add again with the new QR code."
