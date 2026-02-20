#!/usr/bin/env bash
# Check I2S DAC config and list ALSA devices. Run on the Pi.
# Usage: ./scripts/audio-check.sh

CONFIG="/boot/firmware/config.txt"
[[ -f "$CONFIG" ]] || CONFIG="/boot/config.txt"

echo "=== Config: $CONFIG ==="
if [[ -f "$CONFIG" ]]; then
  if grep -qE "dtparam=audio=off" "$CONFIG" 2>/dev/null; then
    echo "On-board audio disabled (dtparam=audio=off) — good for I2S default card."
  else
    echo "Tip: dtparam=audio=off avoids on-board 3.5mm taking default; add if using I2S DAC only."
  fi
  if grep -qE "dtoverlay=(max98357a|hifiberry-dac)" "$CONFIG" 2>/dev/null; then
    echo "I2S overlay found:"
    grep -E "dtoverlay=(max98357a|hifiberry-dac)" "$CONFIG"
  else
    echo "No dtoverlay=max98357a or dtoverlay=hifiberry-dac found."
    echo "Add overlay (BCLK=18, LRC=19, DIN=21). Use no-sdmode so BCM 4 stays free for PIR motion:"
    echo "  echo 'dtoverlay=max98357a,no-sdmode' | sudo tee -a $CONFIG"
    echo "Then reboot: sudo reboot"
  fi
  if grep -q "dtoverlay=max98357a[^,]*$" "$CONFIG" 2>/dev/null; then
    echo ""
    echo "Note: max98357a overlay without no-sdmode uses BCM 4 (conflicts with PIR motion). Add ,no-sdmode or ,sdmode-pin=20."
  fi
else
  echo "Config file not found. Add dtoverlay=max98357a to your boot config and reboot."
fi

echo ""
echo "=== ALSA playback devices (aplay -l) ==="
aplay -l 2>/dev/null || echo "aplay -l failed (no ALSA or no permission)."
