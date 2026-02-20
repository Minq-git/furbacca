#!/usr/bin/env bash
# Check I2S DAC config and list ALSA devices. Run on the Pi.
# Usage: ./scripts/audio-check.sh

CONFIG="/boot/firmware/config.txt"
[[ -f "$CONFIG" ]] || CONFIG="/boot/config.txt"

echo "=== Config: $CONFIG ==="
if [[ -f "$CONFIG" ]]; then
  if grep -qE "dtoverlay=(max98357a|hifiberry-dac)" "$CONFIG" 2>/dev/null; then
    echo "I2S overlay found:"
    grep -E "dtoverlay=(max98357a|hifiberry-dac)" "$CONFIG"
  else
    echo "No dtoverlay=max98357a or dtoverlay=hifiberry-dac found."
    echo "Add overlay (BCLK=18, LRC=19, DIN=21):"
    echo "  echo 'dtoverlay=max98357a' | sudo tee -a $CONFIG"
    echo "Then reboot: sudo reboot"
  fi
else
  echo "Config file not found. Add dtoverlay=max98357a to your boot config and reboot."
fi

echo ""
echo "=== ALSA playback devices (aplay -l) ==="
aplay -l 2>/dev/null || echo "aplay -l failed (no ALSA or no permission)."
