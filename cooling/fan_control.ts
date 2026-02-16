/**
 * Dual-fan cooling harness control (BCM 24 via 2N2222 NPN).
 * Uses pigpio for DMA-based PWM so fans don't jitter when the CPU is busy (e.g. eye rendering).
 *
 * Wiring: BCM 24 (Physical 18) → 1kΩ → transistor base. Emitter to GND, fan between 5V and collector.
 * 1N4001 flyback diode across fan (cathode to 5V). Active-high: HIGH = fans on.
 *
 * Requires: pigpio (npm). On Pi, run as root or start pigpiod: sudo pigpiod
 * Disable: FURBACCA_FAN=0
 */

const FAN_BCM = 24;
const PWM_FREQ_HZ = 25000; // 25 kHz to avoid audible motor whine
const SOFT_START_MS = 2000;
const PWM_MAX = 255; // pigpio duty 0–255 = 0–100%

interface FanGpio {
  digitalWrite(value: number): void;
  pwmFrequency(hz: number): void;
  pwmWrite(duty: number): void;
}
let fanGpio: FanGpio | null = null;
let initialized = false;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Call first, before any other GPIO or heavy work.
 * Sets BCM 24 to OUTPUT and LOW immediately so the fans don't float or flicker.
 */
export function init(): void {
  if (initialized) return;
  if (process.env.FURBACCA_FAN === "0" || process.env.FURBACCA_FAN === "false") return;
  if (process.platform !== "linux") return;

  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const pigpio = require("pigpio");
    const { Gpio } = pigpio;
    const pin = new Gpio(FAN_BCM, { mode: Gpio.OUTPUT });
    fanGpio = pin;
    pin.digitalWrite(0); // Immediate: LOW so fans don't float
    pin.pwmFrequency(PWM_FREQ_HZ);
    pin.pwmWrite(0); // 0% duty
    initialized = true;

    const cleanup = (): void => {
      if (fanGpio) {
        try {
          fanGpio.pwmWrite(0);
          fanGpio.digitalWrite(0);
        } catch {
          /* ignore */
        }
      }
    };
    process.on("exit", cleanup);
    process.on("SIGINT", () => {
      cleanup();
      process.exit(0);
    });
    process.on("SIGTERM", () => {
      cleanup();
      process.exit(0);
    });
  } catch (err) {
    // pigpio not installed, or not on Pi, or pigpiod not running
    fanGpio = null;
  }
}

/**
 * Ramp PWM from 0% to 100% over rampMs to avoid voltage brownout.
 * Call after init(); safe to call even if init() was no-op.
 */
export async function softStart(rampMs: number = SOFT_START_MS): Promise<void> {
  if (!fanGpio || !initialized) return;

  const steps = 100;
  const stepMs = rampMs / steps;
  const dutyPerStep = PWM_MAX / steps;

  for (let i = 1; i <= steps; i++) {
    const duty = Math.round(dutyPerStep * i);
    fanGpio.pwmWrite(Math.min(duty, PWM_MAX));
    await sleep(stepMs);
  }
  fanGpio.pwmWrite(PWM_MAX); // ensure 100%
}

/**
 * Set fan duty 0–100 (percent). Use after softStart for runtime control.
 */
export function setSpeed(percent: number): void {
  if (!fanGpio || !initialized) return;
  const duty = Math.max(0, Math.min(100, Math.round(percent)));
  fanGpio.pwmWrite(Math.round((duty / 100) * PWM_MAX));
}

export const fanControl = { init, softStart, setSpeed };
