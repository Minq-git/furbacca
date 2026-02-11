#!/usr/bin/env bash
# Run vision/eyes.py and blank both displays on exit (Ctrl+C, kill, or normal exit).
# Avoids burn-in when you stop the eyes script.
# Run from repo root. Requires venv activated or python in PATH.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_DIR"

trap 'python3 vision/blank_displays.py' EXIT

exec python3 vision/eyes.py


