#!/usr/bin/env bash
# Download and unzip Vosk small English model for "Hey Furbacca" wake word. Idempotent.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
MODEL_NAME="vosk-model-small-en-us-0.15"
ZIP="${MODEL_NAME}.zip"
URL="https://alphacephei.com/vosk/models/${ZIP}"
DEST_DIR="${REPO_DIR}/voice/models"
MODEL_DIR="${DEST_DIR}/${MODEL_NAME}"

if [[ -d "$MODEL_DIR" ]] && [[ -f "${MODEL_DIR}/am/final.mdl" ]]; then
  echo "Vosk model already at $MODEL_DIR. To refresh: rm -rf $MODEL_DIR && bash .scripts/setup/fetch-vosk-model.sh"
  exit 0
fi

mkdir -p "$DEST_DIR"
cd "$DEST_DIR"
if [[ ! -f "$ZIP" ]]; then
  echo "Downloading Vosk small English model (~40 MB)..."
  wget -q --show-progress "$URL" -O "$ZIP" || { echo "Download failed. Try: wget $URL -O $DEST_DIR/$ZIP"; exit 1; }
fi
echo "Unzipping..."
unzip -o -q "$ZIP" -d "$DEST_DIR"
echo "Done. Model at $MODEL_DIR. Set VOSK_MODEL=$MODEL_DIR or use default voice/models/$MODEL_NAME"
