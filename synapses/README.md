# Synapses — Cross-language UDP contract

Shared JSON message shapes for Furbacca’s Nervous System (Node/TypeScript) and Vision (Python) so both sides stay in sync.

## Ports

| Port | Direction | Purpose |
|------|-----------|---------|
| **5005** | Nervous System → Eyes | Look, animation, blink, eye shape/type, warmup, sleep close |
| **5006** | Camera / eye-track → Nervous System | Eye-tracking events: `looking_started`, `looking_stopped`, `looking_at`, `eye_tracking_started`, `eye_tracking_stopped` |

## Layout

- **synapses/ts/** — TypeScript interfaces for use in `nervous_system.ts` and `vision/ts/eye_bridge.ts`.
- **synapses/py/** — Python dataclasses for use in `vision/py` (main_eyes, camera/camera_track) and scripts that send UDP to the NS.

Update both TS and Python when adding or changing a field so the contract never drifts.
