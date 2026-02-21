# Scripts

## Run these

| Script | When to use |
|--------|-------------|
| **wake-furbacca.sh** | Start everything: eyes + nervous system (touch, sounds, UDP). On the Pi, **eye-tracking** starts by default; use **`--no-eye-track`** or **`FURBACCA_EYE_TRACK=0`** to disable. Run from repo root or alias: `alias wake-furbacca='~/furbacca/scripts/wake-furbacca.sh'`. See README § Troubleshooting if "vision/eyes.py: No such file". |
| **run-eyes.sh** | Eyes only (vision/py/eyes.py). Use when you want eyes in one terminal and nervous system in another. |
| **eye-command.sh** | Send commands to eyes (blink, shape, type) while eyes are running. On Pi: `./scripts/eye-command.sh shape sharp`. From Mac: `./scripts/eye-command.sh furbacca.local type dragon`. |
| **eye-track.sh** | Start/stop/run eye tracking (AI camera → eyes follow you). On Pi: `./scripts/eye-track.sh on` \| `off` \| `status`; `./scripts/eye-track.sh run --print-every 30` for foreground. From Mac: `./scripts/eye-track.sh furbacca.local on`. **eye-track** alias (setup-fresh.sh) runs this script; you can also alias as **fe-track**. Sends UDP to nervous system (127.0.0.1:5006) when tracking is turned on/off. |
| **show-matter-pairing.sh** | Show Matter passcode, manual pairing code, and QR URL from service logs. On Pi: `./scripts/show-matter-pairing.sh`. From Mac: `./scripts/show-matter-pairing.sh furbacca.local` (SSH to Pi). |
| **setup-fresh.sh** | Full Furbacca setup on the Pi (after a wipe): Node.js v20 64-bit if missing, SPI enable, memory tuning, **pigpio + pigpiod** (fan PWM at startup), venv, pip deps, gc9a01py, eye graphics, npm install/build, wake-furbacca alias, and furbacca systemd service (installed, not enabled at boot by default — start manually until stable). Run from repo root: `cd ~/furbacca && bash scripts/setup-fresh.sh`. Idempotent. |

## Used by setup (don’t run directly unless needed)

| Script | Called by | Purpose |
|--------|-----------|---------|
| **setup/fetch-gc9a01py.sh** | setup-fresh.sh | Clone russhughes/gc9a01py into vision/py/gc9a01py. Run manually only if lib/ is missing or you want to refresh the driver. |
| **setup/fetch-eye-graphics.sh** | setup-fresh.sh | Download eye assets (iris, sclera) from Adafruit Pi_Eyes into vision/py/graphics. Run manually to refresh assets. |

## Other

| File | Purpose |
|------|---------|
| **audio-check.sh** | On the Pi: check I2S DAC config (dtoverlay=max98357a or hifiberry-dac in /boot/firmware/config.txt or /boot/config.txt) and list ALSA devices (**aplay -l**). Run: `./scripts/audio-check.sh`. |
| **furbacca.service** | Systemd unit for full stack (wake-furbacca) at boot. Copy to `/etc/systemd/system/`, edit User/WorkingDirectory/ExecStart, then `sudo systemctl enable --now furbacca`. |
| **furbacca-eyes.service** | Systemd unit (eyes only). Use if you want eyes as a service and run the nervous system manually. |
