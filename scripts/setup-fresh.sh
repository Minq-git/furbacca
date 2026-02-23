#!/usr/bin/env bash
# Furbacca full setup: Node (Pi only), vision (venv, pip, gc9a01py, eye graphics), npm deps, optional alias.
# Run from repo root on the Pi after a wipe (or Mac for vision-only). Idempotent (safe to run again).
# One-shot: push-furbacca from Mac, then on Pi: cd ~/furbacca && bash scripts/setup-fresh.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_DIR"

echo "=== Furbacca setup (from $REPO_DIR) ==="

# 0. Node.js (Matter needs 64-bit Node v20+ on the Pi)
UNAME_S=$(uname -s)
UNAME_M=$(uname -m)
NODE_MAJOR=20

if [[ "$UNAME_S" == "Linux" && "$UNAME_M" == "aarch64" ]]; then
  NEED_NODE=false
  if ! command -v node &>/dev/null; then
    NEED_NODE=true
  elif [[ $(node -p "process.arch" 2>/dev/null) != "arm64" ]]; then
    NEED_NODE=true
  else
    NODE_VER=$(node -e "console.log(parseInt(process.version.slice(1).split('.')[0], 10))" 2>/dev/null || echo "0")
    [[ "$NODE_VER" -lt "$NODE_MAJOR" ]] && NEED_NODE=true
  fi

  if [[ "$NEED_NODE" == "true" ]]; then
    echo "Installing Node.js $NODE_MAJOR (64-bit) via NodeSource..."
    sudo apt-get update -qq
    sudo apt-get install -y ca-certificates curl gnupg
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
    echo "deb [arch=arm64 signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" | sudo tee /etc/apt/sources.list.d/nodesource.list >/dev/null
    sudo apt-get update -qq
    sudo apt-get install -y nodejs
    echo "Node: $(node -v) ($(node -p 'process.arch'))."
  else
    echo "Node already OK: $(node -v) ($(node -p 'process.arch'))."
  fi
elif [[ "$UNAME_S" == "Linux" && "$UNAME_M" != "aarch64" ]]; then
  echo "⚠ Not aarch64 ($UNAME_M). Matter needs 64-bit Pi (arm64). Install Node v20+ 64-bit manually if needed."
else
  echo "Skipping Node install (not Linux aarch64). Run npm install/build below for local dev."
fi

# 0b. SPI (eyes need /dev/spidev0.0, /dev/spidev0.1). Enable if not already.
SPI_ENABLED=false
if [[ "$UNAME_S" == "Linux" && ! -c /dev/spidev0.0 ]]; then
  if command -v raspi-config &>/dev/null; then
    echo "Enabling SPI via raspi-config..."
    sudo raspi-config nonint do_spi 0
    SPI_ENABLED=true
    echo "SPI enabled. Reboot to apply: sudo reboot"
  else
    BOOT_CFG=""
    [[ -f /boot/firmware/config.txt ]] && BOOT_CFG=/boot/firmware/config.txt
    [[ -z "$BOOT_CFG" && -f /boot/config.txt ]] && BOOT_CFG=/boot/config.txt
    if [[ -n "$BOOT_CFG" ]] && ! grep -q '^dtparam=spi=on' "$BOOT_CFG" 2>/dev/null; then
      echo "Enabling SPI in $BOOT_CFG..."
      echo "dtparam=spi=on" | sudo tee -a "$BOOT_CFG" >/dev/null
      SPI_ENABLED=true
      echo "SPI enabled. Reboot to apply: sudo reboot"
    fi
  fi
  if [[ "$SPI_ENABLED" != "true" ]]; then
    echo "⚠ SPI not enabled. Run: sudo raspi-config nonint do_spi 0   then: sudo reboot"
  fi
fi

# 0c. Memory tuning for Pi (zram + swap + gpu_mem) so Node/tsc/Matter/vision have headroom
NEED_REBOOT=false
if [[ "$UNAME_S" == "Linux" ]]; then
  # zram: use systemd-zram-generator (Debian Trixie). zram-tools races with kernel/generator — mask it so it never starts.
  # Do not swapoff or unload zram here: that would break the working swap created at boot and the generator does not re-run mid-session.
  sudo systemctl stop zramswap 2>/dev/null || true
  sudo systemctl disable zramswap 2>/dev/null || true
  sudo systemctl mask zramswap 2>/dev/null || true
  if apt-cache show systemd-zram-generator &>/dev/null; then
    if ! dpkg -l systemd-zram-generator &>/dev/null; then
      echo "Installing systemd-zram-generator (compressed RAM swap for Pi Zero 2 W)..."
      sudo apt-get update -qq
      sudo apt-get install -y systemd-zram-generator
    fi
    ZRAM_GEN_CFG=/etc/systemd/zram-generator.conf
    # 100% of RAM, zstd; generator creates swap at boot (no priority option; zram usually before file swap).
    if [[ ! -f "$ZRAM_GEN_CFG" ]] || ! grep -q 'zram-size = ram' "$ZRAM_GEN_CFG" 2>/dev/null || ! grep -q 'compression-algorithm = zstd' "$ZRAM_GEN_CFG" 2>/dev/null; then
      echo "Configuring zram: systemd-zram-generator (100% RAM, zstd)..."
      sudo tee "$ZRAM_GEN_CFG" >/dev/null << 'ZRAMEOF'
# Furbacca: high-compression zram (100% of RAM, zstd). Applied at next boot.
[zram0]
zram-size = ram
compression-algorithm = zstd
ZRAMEOF
      NEED_REBOOT=true
    fi
    echo "zram configured (systemd-zram-generator). Reboot for zram to take effect; then verify with: zramctl"
  else
    echo "systemd-zram-generator not available; zram-tools disabled (known mkswap issues on Pi). Using disk swap only."
  fi
  # Swap: 512 MB if dphys-swapfile is used (fallback; zram is preferred when available)
  if [[ -f /etc/dphys-swapfile ]] && ! grep -q '^CONF_SWAPSIZE=512' /etc/dphys-swapfile 2>/dev/null; then
    CURRENT_SWAP=$(grep -E '^CONF_SWAPSIZE=' /etc/dphys-swapfile 2>/dev/null | sed 's/CONF_SWAPSIZE=//' || echo "0")
    if [[ "${CURRENT_SWAP:-0}" -lt 512 ]]; then
      echo "Increasing swap to 512 MB (was ${CURRENT_SWAP:-100})..."
      if grep -q '^CONF_SWAPSIZE=' /etc/dphys-swapfile; then
        sudo sed -i 's/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=512/' /etc/dphys-swapfile
      else
        echo "CONF_SWAPSIZE=512" | sudo tee -a /etc/dphys-swapfile >/dev/null
      fi
      NEED_REBOOT=true
      echo "Swap will apply after reboot (or: sudo dphys-swapfile swapoff && sudo dphys-swapfile setup && sudo dphys-swapfile swapon)"
    fi
  fi
  # GPU mem: leave more RAM for ARM (headless Furbacca doesn't need much GPU)
  BOOT_CFG=""
  [[ -f /boot/firmware/config.txt ]] && BOOT_CFG=/boot/firmware/config.txt
  [[ -z "$BOOT_CFG" && -f /boot/config.txt ]] && BOOT_CFG=/boot/config.txt
  if [[ -n "$BOOT_CFG" ]]; then
    if grep -q '^gpu_mem=' "$BOOT_CFG" 2>/dev/null; then
      CURRENT_GPU=$(grep '^gpu_mem=' "$BOOT_CFG" | sed 's/gpu_mem=//')
      if [[ "${CURRENT_GPU:-128}" -gt 32 ]]; then
        echo "Reducing gpu_mem to 32 MB (was $CURRENT_GPU) for more ARM RAM..."
        sudo sed -i 's/^gpu_mem=.*/gpu_mem=32/' "$BOOT_CFG"
        NEED_REBOOT=true
      fi
    else
      echo "Setting gpu_mem=32 MB for more ARM RAM..."
      echo "gpu_mem=32" | sudo tee -a "$BOOT_CFG" >/dev/null
      NEED_REBOOT=true
    fi
    # Audio: dtparam=audio=off so I2S DAC is default; max98357a with no-sdmode so BCM 4 free for PIR
    if ! grep -qE '^dtparam=audio=off' "$BOOT_CFG" 2>/dev/null; then
      if grep -qE '^dtparam=audio=' "$BOOT_CFG" 2>/dev/null; then
        echo "Setting dtparam=audio=off in $BOOT_CFG (I2S default)..."
        sudo sed -i 's/^dtparam=audio=.*/dtparam=audio=off/' "$BOOT_CFG"
      else
        echo "Adding dtparam=audio=off to $BOOT_CFG (I2S default)..."
        echo "dtparam=audio=off" | sudo tee -a "$BOOT_CFG" >/dev/null
      fi
      NEED_REBOOT=true
    fi
    if ! grep -qE 'dtoverlay=(max98357a|hifiberry-dac)' "$BOOT_CFG" 2>/dev/null; then
      echo "Adding dtoverlay=max98357a,no-sdmode to $BOOT_CFG (BCLK 18, LRC 19, DIN 21; BCM 4 free for PIR)..."
      echo "dtoverlay=max98357a,no-sdmode" | sudo tee -a "$BOOT_CFG" >/dev/null
      NEED_REBOOT=true
    elif grep 'dtoverlay=max98357a' "$BOOT_CFG" 2>/dev/null | grep -qv 'no-sdmode'; then
      echo "Replacing max98357a overlay with no-sdmode in $BOOT_CFG (free BCM 4 for PIR)..."
      sudo sed -i 's/^dtoverlay=max98357a.*/dtoverlay=max98357a,no-sdmode/' "$BOOT_CFG"
      NEED_REBOOT=true
    fi
  fi
  if [[ "$NEED_REBOOT" == "true" ]]; then
    echo "Reboot now so zram/swap/gpu_mem/audio config apply, then re-run this script to complete setup (npm install + build): sudo reboot"
    echo "After reboot: cd $REPO_DIR && bash scripts/setup-fresh.sh"
    exit 0
  fi
fi

# 1. Build deps (Python.h + gcc for spidev/RPi.GPIO; git for gc9a01py; libgpiod for fan; AI camera IMX500)
if [[ "$UNAME_S" == "Linux" ]]; then
  echo "Ensuring Python dev headers, build tools, git, and libgpiod..."
  sudo apt-get update -qq
  sudo apt-get install -y python3-dev python3-setuptools build-essential git
  # libgpiod: GPIO character device for cooling fan (BCM 24). Debian Trixie: gpiod + libgpiod-dev.
  sudo apt-get install -y gpiod libgpiod-dev
  # Raspberry Pi AI Camera (IMX500): latest system + firmware so CSI camera works (face/object tracking).
  echo "Ensuring Raspberry Pi AI Camera deps (apt full-upgrade + imx500-all)..."
  sudo apt-get update -qq
  sudo apt-get full-upgrade -y
  sudo apt-get install -y imx500-all python3-picamera2 python3-opencv
  echo "AI camera (imx500-all), python3-picamera2, and python3-opencv installed. Reboot once so IMX500 firmware loads (see https://www.raspberrypi.com/documentation/accessories/ai-camera.html)."
fi

# 2. Python venv
if [[ ! -d env ]]; then
  echo "Creating venv..."
  python3 -m venv env
else
  echo "Venv already exists."
fi

# 3. Activate and pip install (vision/py/eyes.py deps)
echo "Installing pip packages (spidev/RPi.GPIO may take a few minutes to compile on the Pi)..."
# shellcheck source=/dev/null
source env/bin/activate
pip install --quiet --upgrade pip
pip install spidev RPi.GPIO Pillow numpy

# 4. Fetch gc9a01py driver (required for vision/py/eyes.py)
echo "Fetching gc9a01py driver..."
bash scripts/setup/fetch-gc9a01py.sh

# 5. Fetch eye graphics (iris.jpg, eye.svg, sclera.png, etc. into vision/py/graphics)
echo "Fetching eye graphics..."
bash scripts/setup/fetch-eye-graphics.sh

# 6. Node deps (nervous system)
echo "Installing npm deps and building..."
# node-gyp (node-libgpiod) needs Python with distutils; use system Python, not venv (venv may be 3.12+ without distutils)
[[ "$UNAME_S" == "Linux" ]] && export npm_config_python=/usr/bin/python3
npm install
# On Pi (low RAM), use build:pi (450 MB heap); with zram active after reboot, tsc can complete.
if [[ "$UNAME_S" == "Linux" ]]; then
  # Avoid OOM: require zram to be active before running tsc (generator only creates it at boot).
  if [[ "$UNAME_M" == "aarch64" ]] && ! grep -q '/dev/zram' /proc/swaps 2>/dev/null; then
    echo "⚠ zram is not active (zramctl shows nothing). The TypeScript build will likely OOM."
    echo "  Reboot first so zram starts, then re-run: sudo reboot"
    echo "  After reboot: cd $REPO_DIR && bash scripts/setup-fresh.sh"
    echo "  Or build on Mac and push: npm run build && ./scripts/push-furbacca.sh"
    exit 1
  fi
  echo "Building TypeScript (2–5 min on Pi Zero 2 W, no output until done — please wait)..."
  if ! npm run build:pi; then
    echo "⚠ Pi build failed (often OOM). Reboot so zram is active, then re-run setup-fresh; or build on Mac: npm run build && push-furbacca"
    exit 1
  fi
else
  npm run build
fi
npm run sync-sounds

# 7. Optional: wake-furbacca alias (only on Pi, only if not already set)
if [[ "$UNAME_S" == "Linux" ]]; then
  RC=""
  [[ -f ~/.zshrc ]] && RC=~/.zshrc
  [[ -z "$RC" && -f ~/.bashrc ]] && RC=~/.bashrc
  if [[ -n "$RC" ]]; then
    if ! grep -q "wake-furbacca" "$RC" 2>/dev/null; then
      LINE="alias wake-furbacca='$REPO_DIR/scripts/wake-furbacca.sh'"
      echo "" >> "$RC"
      echo "# Furbacca" >> "$RC"
      echo "$LINE" >> "$RC"
      echo "Added to $RC: $LINE"
    fi
    if ! grep -q "sleep-furbacca" "$RC" 2>/dev/null; then
      echo "alias sleep-furbacca='sudo halt'" >> "$RC"
      echo "Added to $RC: alias sleep-furbacca='sudo halt'"
    fi
    if ! grep -q "setup-furbacca" "$RC" 2>/dev/null; then
      echo "alias setup-furbacca='bash $REPO_DIR/scripts/setup-fresh.sh'" >> "$RC"
      echo "Added to $RC: alias setup-furbacca='...'"
    fi
    if ! grep -q "eye-track" "$RC" 2>/dev/null; then
      echo "alias eye-track='$REPO_DIR/scripts/eye-track.sh'" >> "$RC"
      echo "Added to $RC: alias eye-track='...'"
    fi
  fi

  # 7b. Wi‑Fi config backup for network heal (head+belly 30s after brownout)
  # Bookworm/Trixie often use NetworkManager; config is in /etc/NetworkManager/system-connections/*.nmconnection
  BOOT_PARTITION=""
  for b in /boot/firmware /boot; do [[ -d "$b" ]] && BOOT_PARTITION="$b" && break; done
  if [[ -f /etc/wpa_supplicant/wpa_supplicant.conf ]]; then
    if [[ -n "$BOOT_PARTITION" ]]; then
      sudo cp /etc/wpa_supplicant/wpa_supplicant.conf "$BOOT_PARTITION/wpa_supplicant.conf" 2>/dev/null && \
        echo "Backed up wpa_supplicant.conf to $BOOT_PARTITION (for scripts/heal-network.sh)." || \
        echo "⚠ Could not write $BOOT_PARTITION/wpa_supplicant.conf (e.g. read-only). After first boot, run: sudo cp /etc/wpa_supplicant/wpa_supplicant.conf $BOOT_PARTITION/"
    else
      echo "⚠ Boot partition not writable. When Wi‑Fi is configured, run: sudo cp /etc/wpa_supplicant/wpa_supplicant.conf /boot/"
    fi
  elif [[ -d /etc/NetworkManager/system-connections ]] && ls /etc/NetworkManager/system-connections/*.nmconnection 1>/dev/null 2>&1; then
    FIRST_NM=$(ls /etc/NetworkManager/system-connections/*.nmconnection 2>/dev/null | head -n1)
    if [[ -n "$FIRST_NM" && -n "$BOOT_PARTITION" ]]; then
      sudo cp "$FIRST_NM" "$BOOT_PARTITION/NetworkManager-connection.nmconnection" 2>/dev/null && \
        echo "Backed up NetworkManager Wi‑Fi to $BOOT_PARTITION/NetworkManager-connection.nmconnection (heal-network will restore on head+belly 30s)." || \
        echo "⚠ Could not write to $BOOT_PARTITION. To backup Wi‑Fi manually: sudo cp $FIRST_NM $BOOT_PARTITION/NetworkManager-connection.nmconnection"
    else
      echo "Wi‑Fi is in NetworkManager (no wpa_supplicant.conf). To backup for heal: sudo cp /etc/NetworkManager/system-connections/*.nmconnection /boot/NetworkManager-connection.nmconnection"
    fi
  else
    echo "Skipping Wi‑Fi backup (no wpa_supplicant.conf or NetworkManager connections). When Wi‑Fi is configured, backup with: sudo cp /etc/wpa_supplicant/wpa_supplicant.conf /boot/   or (NetworkManager): sudo cp /etc/NetworkManager/system-connections/*.nmconnection /boot/NetworkManager-connection.nmconnection"
  fi

  # 8. Optional: install furbacca systemd service (not enabled at boot — start manually until stable)
  FURBACCA_USER="${SUDO_USER:-$USER}"
  if [[ -z "$FURBACCA_USER" ]]; then
    FURBACCA_USER=$(whoami)
  fi
  SVC_FILE=/etc/systemd/system/furbacca.service
  if ! [[ -f "$SVC_FILE" ]] || ! grep -q "$REPO_DIR" "$SVC_FILE" 2>/dev/null; then
    echo "Installing furbacca systemd service (not set to start at boot)..."
    sudo tee "$SVC_FILE" >/dev/null << EOF
# Furbacca full stack (eyes + nervous system). Generated by setup-fresh.sh
[Unit]
Description=Furbacca (eyes + nervous system, touch, Matter)
After=network.target

[Service]
Type=simple
User=$FURBACCA_USER
WorkingDirectory=$REPO_DIR
ExecStart=$REPO_DIR/scripts/wake-furbacca.sh
Restart=on-failure
RestartSec=10
StartLimitIntervalSec=300
StartLimitBurst=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl disable furbacca 2>/dev/null || true
    echo "Service installed. Start manually: sudo systemctl start furbacca   or: wake-furbacca   When stable, enable at boot: sudo systemctl enable furbacca"
  else
    echo "furbacca service already installed."
    sudo systemctl disable furbacca 2>/dev/null || true
    echo "Service not set to start at boot. Start manually: sudo systemctl start furbacca   or: wake-furbacca   When stable: sudo systemctl enable furbacca"
  fi
fi

echo ""
echo "=== Setup complete ==="
echo "Run: ./scripts/wake-furbacca.sh   (or: wake-furbacca   after opening a new shell)"
echo "Re-run full setup: setup-furbacca   (alias added to your shell rc)"
echo "SPI / pinout: instruction.md §3.1."
