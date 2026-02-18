#!/usr/bin/env bash
# Remove Matter storage (.matter/) so the device is uncommissioned. Run from repo root.
# Usage: ./scripts/matter-factory-reset.sh [-y]
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_DIR"
MATTER_DIR="$REPO_DIR/.matter"
if [[ "$1" != "-y" ]]; then
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
