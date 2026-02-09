#!/usr/bin/env bash
# Run the GC9A01 fbx2 eye copy (Option A). Must be run on the Pi after setup-fbx2-gc9a01.sh.
# Usage: ./vision/run-eyes-fbx2.sh   or:  sudo vision/pi-eyes-gc9a01a/fbx2 -g

set -e
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FBX2="${REPO_DIR}/vision/pi-eyes-gc9a01a/fbx2"

if [[ ! -x "$FBX2" ]]; then
  echo "fbx2 not found. Run first: ./scripts/setup-fbx2-gc9a01.sh"
  exit 1
fi

exec sudo "$FBX2" -g "$@"
