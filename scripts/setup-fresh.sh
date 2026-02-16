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

# 1. Build deps (Python.h + gcc for spidev/RPi.GPIO; git for gc9a01py)
if [[ "$UNAME_S" == "Linux" ]]; then
  echo "Ensuring Python dev headers, build tools, and git..."
  sudo apt-get update -qq
  sudo apt-get install -y python3-dev build-essential git
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
npm install
# On Pi (low RAM), limit Node heap so tsc doesn't OOM
[[ "$UNAME_S" == "Linux" ]] && export NODE_OPTIONS=--max-old-space-size=384
npm run build

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
  fi

  # 8. Optional: install and enable furbacca systemd service (start at boot)
  FURBACCA_USER="${SUDO_USER:-$USER}"
  if [[ -z "$FURBACCA_USER" ]]; then
    FURBACCA_USER=$(whoami)
  fi
  SVC_FILE=/etc/systemd/system/furbacca.service
  if ! [[ -f "$SVC_FILE" ]] || ! grep -q "$REPO_DIR" "$SVC_FILE" 2>/dev/null; then
    echo "Installing furbacca systemd service (start at boot)..."
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
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable --now furbacca
    echo "Service enabled and started (runs now and at boot). Status: sudo systemctl status furbacca"
  else
    echo "furbacca service already installed. Start: sudo systemctl start furbacca   Status: sudo systemctl status furbacca"
  fi
fi

echo ""
echo "=== Setup complete ==="
echo "Run: ./scripts/wake-furbacca.sh   (or: wake-furbacca   after opening a new shell)"
echo "SPI / pinout: instruction.md §3.1."
