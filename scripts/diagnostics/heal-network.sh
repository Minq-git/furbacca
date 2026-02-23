#!/usr/bin/env bash
# scripts/diagnostics/heal-network.sh — Emergency network repair after brownout.
# Restarts network stack and optionally restores wpa_supplicant from /boot backup.
# Trigger: Head + Belly held 30s (nervous_system.ts). Prep: sudo cp /etc/wpa_supplicant/wpa_supplicant.conf /boot/wpa_supplicant.conf

set -e
LOG="${HOME:-/home/minqz}/network_heal.log"
echo "$(date): Starting network heal..." >> "$LOG"

# 1. Software restart of network stack (NetworkManager on Bookworm, dhcpcd on Bullseye)
sudo systemctl restart NetworkManager 2>/dev/null || sudo systemctl restart dhcpcd 2>/dev/null || true
sudo ip link set wlan0 down 2>/dev/null && sleep 2 && sudo ip link set wlan0 up 2>/dev/null || true

# 2. Nuclear option: restore Wi‑Fi config from boot backup (often survives brownout)
for boot in /boot/firmware /boot; do
  if [[ -f "$boot/wpa_supplicant.conf" ]]; then
    echo "$(date): Restoring wpa_supplicant from $boot backup..." >> "$LOG"
    sudo cp "$boot/wpa_supplicant.conf" /etc/wpa_supplicant/wpa_supplicant.conf
    sudo wpa_cli -i wlan0 reconfigure 2>/dev/null || true
    break
  fi
done
# NetworkManager (Bookworm/Trixie): restore from .nmconnection backup if no wpa_supplicant backup
if [[ ! -f /boot/wpa_supplicant.conf && ! -f /boot/firmware/wpa_supplicant.conf ]]; then
  for boot in /boot/firmware /boot; do
    if [[ -f "$boot/NetworkManager-connection.nmconnection" ]]; then
      echo "$(date): Restoring NetworkManager Wi‑Fi from $boot backup..." >> "$LOG"
      sudo cp "$boot/NetworkManager-connection.nmconnection" /etc/NetworkManager/system-connections/furbacca-restore.nmconnection
      sudo chmod 600 /etc/NetworkManager/system-connections/furbacca-restore.nmconnection
      sudo nmcli connection reload 2>/dev/null || true
      break
    fi
  done
fi

echo "$(date): Heal complete." >> "$LOG"
