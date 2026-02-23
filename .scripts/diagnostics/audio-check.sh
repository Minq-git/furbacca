#!/usr/bin/env bash
# Check I2S DAC config and list ALSA devices. Run on the Pi.
# Usage: ./.scripts/diagnostics/audio-check.sh

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

echo ""
echo "=== If aplay runs but no sound from I2S speakers ==="
echo "1. Reboot: sudo reboot (I2S driver sometimes needs a clean slate)."
echo "2. Full power cycle: unplug Pi power 5–10 seconds, then plug back in."
echo "3. Test tone on card 0: speaker-test -D plughw:0,0 -c 1 -t sine -f 440 -l 1"
echo "4. Volume (if card has controls): amixer -c 0 sset PCM 100%"
echo "5. From repo root, WAV test: aplay -D plughw:0,0 voice/assets/giggle.wav"
echo "6. If sound stopped after wake-furbacca: fixed by not using BCM 18 for display backlight (vision/py/display.py). If it recurs: reboot or see README."
