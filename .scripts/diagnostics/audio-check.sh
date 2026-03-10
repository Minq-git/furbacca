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
  # Furbacca: MAX98357A (DAC) + I2S mic on GPIO 20 (e.g. SPH0645). Common: max98357a or asoc-simple-card for DAC, googlevoicehat-soundcard for mic.
  if grep -qE "dtoverlay=googlevoicehat-soundcard" "$CONFIG" 2>/dev/null && grep -qE "dtoverlay=(max98357a|asoc-simple-card)" "$CONFIG" 2>/dev/null; then
    echo "I2S overlays: DAC (max98357a or asoc-simple-card) + googlevoicehat-soundcard (mic on GPIO 20). Run arecord -l; set FURBACCA_MIC_CARD if capture is not on card 0."
    grep -E "dtoverlay=(max98357a|googlevoicehat|asoc-simple-card)" "$CONFIG"
  elif grep -qE "dtoverlay=(max98357a|asoc-simple-card|googlevoicehat-soundcard|hifiberry-dac|furbacca-audio)" "$CONFIG" 2>/dev/null; then
    echo "I2S overlay found:"
    grep -E "dtoverlay=(max98357a|asoc-simple-card|googlevoicehat-soundcard|hifiberry-dac|furbacca-audio)" "$CONFIG" 2>/dev/null || true
    if grep -qE "dtoverlay=(max98357a|asoc-simple-card)" "$CONFIG" 2>/dev/null && ! grep -qE "dtoverlay=(googlevoicehat|furbacca-audio)" "$CONFIG" 2>/dev/null; then
      echo "  (DAC only. For hearing, add dtoverlay=googlevoicehat-soundcard for I2S mic on GPIO 20; see README.)"
    fi
  else
    echo "No I2S overlay found. Add DAC overlay and dtoverlay=googlevoicehat-soundcard for mic; see README."
  fi
  if grep -q "dtoverlay=max98357a[^,]*$" "$CONFIG" 2>/dev/null; then
    echo ""
    echo "Note: max98357a without no-sdmode uses BCM 4 (conflicts with PIR). Add ,no-sdmode if needed."
  fi
else
  echo "Config file not found. Add dtparam=i2s=on and your audio overlay (MAX98357A + I2S mic); see README."
fi

echo ""
echo "=== ALSA playback (aplay -l) ==="
aplay -l 2>/dev/null || echo "aplay -l failed (no ALSA or no permission)."
echo ""
echo "=== ALSA capture (arecord -l) — needed for hearing ==="
arecord -l 2>/dev/null || echo "arecord -l failed (no capture device or no permission)."
if ! arecord -l 2>/dev/null | grep -q "card.*device"; then
  echo "  No capture device — add dtoverlay=googlevoicehat-soundcard for I2S mic on GPIO 20 (see README), or use a combined overlay."
fi

echo ""
echo "=== If aplay runs but no sound from I2S speakers ==="
echo "1. Reboot: sudo reboot (I2S driver sometimes needs a clean slate)."
echo "2. Full power cycle: unplug Pi power 5–10 seconds, then plug back in."
echo "3. Test tone on card 0: speaker-test -D plughw:0,0 -c 1 -t sine -f 440 -l 1"
echo "4. Volume (if card has controls): amixer -c 0 sset PCM 100%"
echo "5. From repo root, WAV test: aplay -D plughw:0,0 voice/assets/giggle.wav"
echo "6. If sound stopped after wake-furbacca: fixed by not using BCM 18 for display backlight (vision/py/display.py). If it recurs: reboot or see README."
