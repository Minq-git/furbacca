# Scripts

## Run these

| Script | When to use |
|--------|-------------|
| **wake-furbacca.sh** | Start everything: eyes + nervous system (touch, sounds, UDP). Run from repo root or alias on the Pi: `alias wake-furbacca='~/furbacca/scripts/wake-furbacca.sh'`. If you get "vision/eyes.py: No such file", your alias/script points to the old path—see README § Troubleshooting. |
| **run-eyes.sh** | Eyes only (vision/py/eyes.py). Use when you want eyes in one terminal and nervous system in another. |
| **eye-command.sh** | Send commands to eyes (blink, shape, type) while eyes are running. On Pi: `./scripts/eye-command.sh shape sharp`. From Mac: `./scripts/eye-command.sh furbacca.local type dragon`. |
| **show-matter-pairing.sh** | On the Pi: show Matter passcode, manual pairing code, and QR URL from furbacca service logs. Use when the service started at boot and the pairing QR scrolled past. |
| **setup-fresh.sh** | Full Furbacca setup on the Pi (after a wipe): Node.js v20 64-bit if missing, SPI enable, venv, pip deps, gc9a01py, eye graphics, npm install/build, wake-furbacca alias, and furbacca systemd service (start at boot). Run from repo root: `cd ~/furbacca && bash scripts/setup-fresh.sh`. Idempotent. |

## Used by setup (don’t run directly unless needed)

| Script | Called by | Purpose |
|--------|-----------|---------|
| **setup/fetch-gc9a01py.sh** | setup-fresh.sh | Clone russhughes/gc9a01py into vision/py/gc9a01py. Run manually only if lib/ is missing or you want to refresh the driver. |
| **setup/fetch-eye-graphics.sh** | setup-fresh.sh | Download eye assets (iris, sclera) from Adafruit Pi_Eyes into vision/py/graphics. Run manually to refresh assets. |

## Other

| File | Purpose |
|------|---------|
| **furbacca.service** | Systemd unit for full stack (wake-furbacca) at boot. Copy to `/etc/systemd/system/`, edit User/WorkingDirectory/ExecStart, then `sudo systemctl enable --now furbacca`. |
| **furbacca-eyes.service** | Systemd unit (eyes only). Use if you want eyes as a service and run the nervous system manually. |
