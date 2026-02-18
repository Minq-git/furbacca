#!/usr/bin/env bash
# scripts/heal-network.sh — Emergency network repair after brownout.
# Restarts network stack and optionally restores wpa_supplicant from /boot backup.
# Trigger: Head + Belly held 30s (nervous_system.ts). Prep: sudo cp /etc/wpa_supplicant/wpa_supplicant.conf /boot/wpa_supplicant.conf

set -e
LOG="${HOME:-/home/minqz}/network_heal.log"
echo "$(date): Starting network heal..." >> "$LOG"

# 1. Software restart of network stack (NetworkManager on Bookworm, dhcpcd on Bullseye)
sudo systemctl restart NetworkManager 2>/dev/null || sudo systemctl restart dhcpcd 2>/dev/null || true
sudo ip link set wlan0 down 2>/dev/null && sleep 2 && sudo ip link set wlan0 up 2>/dev/null || true

# 2. Nuclear option: restore Wi‑Fi config from boot backup (often survives brownout)
if [[ -f /boot/wpa_supplicant.conf ]]; then
  echo "$(date): Restoring wifi config from boot backup..." >> "$LOG"
  sudo cp /boot/wpa_supplicant.conf /etc/wpa_supplicant/wpa_supplicant.conf
  sudo wpa_cli -i wlan0 reconfigure 2>/dev/null || true
fi

echo "$(date): Heal complete." >> "$LOG"
