#!/usr/bin/env bash
# Fetch russhughes/gc9a01py into vision/gc9a01py (pure-Python GC9A01 driver for MicroPython; we use it via CPython compat layer).
set -e
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${REPO_ROOT}/vision/gc9a01py"
URL="https://github.com/russhughes/gc9a01py.git"

if [[ -d "${DEST}/.git" ]]; then
  echo "vision/gc9a01py already cloned. To refresh: rm -rf vision/gc9a01py && bash scripts/fetch-gc9a01py.sh"
  exit 0
fi

echo "Cloning gc9a01py into ${DEST}..."
mkdir -p "$(dirname "$DEST")"
git clone --depth 1 "$URL" "$DEST"
echo "Done. Driver is at vision/gc9a01py/lib/gc9a01py.py"
