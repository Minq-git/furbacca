# Scripts

## Run these

| Script | When to use |
|--------|-------------|
| **wake-furbacca.sh** | Start everything: eyes + nervous system (touch, sounds, UDP). One command; run from repo root or alias it. |
| **run-eyes.sh** | Eyes only (vision/py/eyes.py). Use when you want eyes in one terminal and nervous system in another. |
| **eye-command.sh** | Send commands to eyes (blink, shape, type) while eyes are running. On Pi: `./scripts/eye-command.sh shape sharp`. From Mac: `./scripts/eye-command.sh furbacca.local type dragon`. |
| **setup-fresh.sh** | One-time (or re-run) setup on the Pi: venv, pip deps, gc9a01py driver, eye graphics. Run from repo root. |

## Used by setup (don’t run directly unless needed)

| Script | Called by | Purpose |
|--------|-----------|---------|
| **setup/fetch-gc9a01py.sh** | setup-fresh.sh | Clone russhughes/gc9a01py into vision/py/gc9a01py. Run manually only if lib/ is missing or you want to refresh the driver. |
| **setup/fetch-eye-graphics.sh** | setup-fresh.sh | Download eye assets (iris, sclera) from Adafruit Pi_Eyes into vision/py/graphics. Run manually to refresh assets. |

## Other

| File | Purpose |
|------|---------|
| **furbacca-eyes.service** | Systemd unit template (eyes only). Copy to `/etc/systemd/system/` and edit paths if you want eyes as a service instead of wake-furbacca. |
