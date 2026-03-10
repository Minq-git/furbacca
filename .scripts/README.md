# Scripts

## Layout

```text
.scripts/
├── wake-furbacca.sh             # Main entry point (eyes + nervous system)
├── fe-restart.sh                # Quick panic-button reset (UDP restart_both)
├── README.md                    # This file
│
├── setup/                       # Installation & environment
│   ├── setup-fresh.sh
│   ├── fetch-eye-graphics.sh
│   └── fetch-gc9a01py.sh
│
├── diagnostics/                 # Health checks & hardware tests (the "Vet")
│   ├── audio-check.sh
│   ├── monitor-zram.sh
│   ├── heal-network.sh
│   └── (test-fan: see homeostasis/test-fan.ts)
│
├── matter/                      # Smart home / ecosystem utilities
│   ├── show-matter-pairing.sh
│   └── matter-factory-reset.sh
│
├── vision/                      # Tools for the optical system
│   ├── run-eyes.sh              # Headless/standalone eye execution
│   ├── eye-command.sh           # UDP command sender
│   └── eye-track.sh             # Picamera2 execution
│
└── systemd/                     # OS-level service definitions
    ├── furbacca.service
    └── furbacca-eyes.service
```

## Root scripts

| Script | When to use |
| ------ | ----------- |
| **wake-furbacca.sh** | Start everything: eyes + nervous system (touch, voice, UDP). On the Pi, **eye-tracking** starts by default; use **`--no-eye-track`** or **`FURBACCA_EYE_TRACK=0`** to disable. Run from repo root or alias: `alias wake-furbacca='~/furbacca/.scripts/wake-furbacca.sh'`. |
| **fe-restart.sh** | Send UDP `restart_both` to eyes (full hardware re-init). On Pi: `./.scripts/fe-restart.sh`. From Mac: `./.scripts/fe-restart.sh furbacca.local`. Same as head + belly 5 s. |

## setup/

| Script | Purpose |
| ------ | ------- |
| **setup-fresh.sh** | Full Furbacca setup on the Pi (after a wipe): Node.js v20 64-bit if missing, SPI, memory tuning, pigpio + pigpiod, venv, pip deps, gc9a01py, eye graphics, npm install/build, wake-furbacca alias, furbacca systemd service (installed, not enabled at boot). Run: `cd ~/furbacca && bash .scripts/setup/setup-fresh.sh`. Idempotent. |
| **fetch-gc9a01py.sh** | Clone russhughes/gc9a01py into vision/py/gc9a01py. Run manually if lib/ is missing. |
| **fetch-eye-graphics.sh** | Download eye assets into vision/py/assets/graphics. Run manually to refresh. |

## diagnostics/

| Script | Purpose |
| ------ | ------- |
| **audio-check.sh** | On the Pi: check I2S DAC config and list ALSA devices. Run: `./.scripts/diagnostics/audio-check.sh`. |
| **monitor-zram.sh** | Live zRAM and swap monitor. On Pi: `./.scripts/diagnostics/monitor-zram.sh`. From Mac: `./.scripts/diagnostics/monitor-zram.sh furbacca.local`. |
| **heal-network.sh** | Emergency network repair (belly 15 s triggers from nervous system). Run manually: `./.scripts/diagnostics/heal-network.sh`. |
| **test-fan** | Test fan on BCM 26. After build: `npm run test-fan` or `node dist/homeostasis/test-fan.js`. Source: `homeostasis/test-fan.ts`. |

## matter/

| Script | Purpose |
| ------ | ------- |
| **show-matter-pairing.sh** | Show Matter passcode, manual pairing code, QR URL from service logs. On Pi: `./.scripts/matter/show-matter-pairing.sh`. From Mac: `./.scripts/matter/show-matter-pairing.sh furbacca.local`. |
| **matter-factory-reset.sh** | Clear `.matter/` so device appears uncommissioned. Run: `./.scripts/matter/matter-factory-reset.sh [-y]`. |

## vision/

| Script | Purpose |
| ------ | ------- |
| **run-eyes.sh** | Eyes only. Use when you want eyes in one terminal and nervous system in another. Run: `./.scripts/vision/run-eyes.sh`. |
| **eye-command.sh** | Send UDP commands to eyes (blink, shape, type). On Pi: `./.scripts/vision/eye-command.sh shape sharp`. From Mac: `./.scripts/vision/eye-command.sh furbacca.local type dragon`. |
| **eye-track.sh** | Start/stop/run eye tracking (AI camera). On Pi: `./.scripts/vision/eye-track.sh on` \| `off` \| `status`; foreground: `./.scripts/vision/eye-track.sh run --print-every 30`. From Mac: `./.scripts/vision/eye-track.sh furbacca.local on`. **eye-track** alias (setup-fresh) runs this. Sends UDP to NS (127.0.0.1:5006) when on/off. |

## systemd/

| File | Purpose |
| ---- | ------- |
| **furbacca.service** | Full stack (wake-furbacca) at boot. setup-fresh installs it (not enabled by default). Manual: `sudo cp .scripts/systemd/furbacca.service /etc/systemd/system/`, edit User/WorkingDirectory/ExecStart, then `sudo systemctl daemon-reload && sudo systemctl enable --now furbacca`. |
| **furbacca-eyes.service** | Eyes only. Use if you run the nervous system manually. |
