#!/usr/bin/env bash
# .scripts/diagnostics/heal-network.sh — Emergency network repair after brownout.
# Restarts network stack and optionally restores Wi‑Fi config from /boot backups.
# Trigger: Head + Belly held 30s (nervous_system.ts).

set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
  exit 0
fi

_log_path() {
  # Prefer the invoking user's HOME when run under sudo.
  if [[ -n "${SUDO_USER:-}" ]]; then
    local home
    home="$(getent passwd "$SUDO_USER" 2>/dev/null | cut -d: -f6 || true)"
    if [[ -n "$home" ]]; then
      echo "$home/network_heal.log"
      return
    fi
  fi
  echo "${HOME:-/home/minqz}/network_heal.log"
}

LOG="$(_log_path)"
mkdir -p "$(dirname "$LOG")" 2>/dev/null || true

log() {
  printf "%s: %s\n" "$(date)" "$*" >> "$LOG"
}

log "Starting network heal..."

# 1. Software restart of network stack (NetworkManager on Bookworm, dhcpcd on Bullseye)
sudo systemctl restart NetworkManager 2>/dev/null || sudo systemctl restart dhcpcd 2>/dev/null || true
sudo ip link set wlan0 down 2>/dev/null && sleep 2 && sudo ip link set wlan0 up 2>/dev/null || true

BOOT_CANDIDATES=(/boot/firmware /boot)

restored_wpa=0
for boot in "${BOOT_CANDIDATES[@]}"; do
  if [[ -f "$boot/wpa_supplicant.conf" ]]; then
    log "Restoring wpa_supplicant from $boot backup..."
    sudo cp "$boot/wpa_supplicant.conf" /etc/wpa_supplicant/wpa_supplicant.conf
    sudo wpa_cli -i wlan0 reconfigure 2>/dev/null || true
    restored_wpa=1
    break
  fi
done

if [[ "$restored_wpa" -eq 0 ]]; then
  # NetworkManager (Bookworm/Trixie): restore from keyfile backup.
  for boot in "${BOOT_CANDIDATES[@]}"; do
    if [[ -f "$boot/NetworkManager-connection.nmconnection" ]]; then
      log "Restoring NetworkManager Wi‑Fi from $boot backup..."
      sudo mkdir -p /etc/NetworkManager/system-connections 2>/dev/null || true
      sudo cp "$boot/NetworkManager-connection.nmconnection" \
        /etc/NetworkManager/system-connections/furbacca-restore.nmconnection
      sudo chmod 600 /etc/NetworkManager/system-connections/furbacca-restore.nmconnection
      sudo nmcli connection reload 2>/dev/null || true
      break
    fi
  done
fi

# Netplan fallback: some systems have no keyfile (*.nmconnection) even when NetworkManager is active.
# If we backed up /etc/netplan/*.yaml to boot, restore and apply.
if [[ "$restored_wpa" -eq 0 ]] && [[ -d /etc/netplan ]]; then
  for boot in "${BOOT_CANDIDATES[@]}"; do
    shopt -s nullglob
    yaml_files=("$boot"/*.yaml)
    shopt -u nullglob
    if (( ${#yaml_files[@]} > 0 )); then
      log "Restoring netplan YAML(s) from $boot backup..."
      sudo cp "${yaml_files[@]}" /etc/netplan/ 2>/dev/null || true
      sudo netplan apply 2>/dev/null || true
      sudo systemctl restart NetworkManager 2>/dev/null || true
      break
    fi
  done
fi

log "Heal complete."
