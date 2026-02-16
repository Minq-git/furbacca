/**
 * Dual-fan cooling harness control (BCM 24 via 2N2222 NPN).
 * Uses libgpiod (easy-gpiod, libgpiod 2.x) and software PWM so fans run without a daemon.
 *
 * Wiring: BCM 24 (Physical 18) → 1kΩ → transistor base. Emitter to GND, fan between 5V and collector.
 * 1N4001 flyback diode across fan (cathode to 5V). Active-high: HIGH = fans on.
 *
 * BCM 24 has no hardware PWM on Pi Zero 2; PWM is software (fixed period, duty in userspace).
 * Soft-start ramps 0%→100% over 2 s to avoid voltage brownout.
 *
 * Requires: gpiod + libgpiod-dev (apt), easy-gpiod (npm). Debian Trixie: libgpiod 2.x, GPIO character device.
 * Disable: FURBACCA_FAN=0
 */

const FAN_BCM = 24;
const SOFT_START_MS = 2000;
/** Software PWM period (ms). ~100 Hz to keep timing stable under SPI/CPU load. */
const PWM_PERIOD_MS = 10;

interface LineLike {
  setValue(value: number): void;
  release?(): void;
}

/** Hold references so GC doesn't release (easy-gpiod requirement). */
let fanChip: { close: () => void } | null = null;
let fanRequest: { close: () => void; lines: { fan: { value: boolean } } } | null = null;
let fanLine: LineLike | null = null;
let initialized = false;
/** Target duty 0–100 (percent). Used by the PWM tick. */
let targetDutyPercent = 0;
let pwmInterval: ReturnType<typeof setInterval> | null = null;
let pwmTimeout: ReturnType<typeof setTimeout> | null = null;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * One PWM period: set line high, then low after duty fraction of period.
 * Called every PWM_PERIOD_MS by setInterval.
 */
function pwmTick(): void {
  const line = fanLine;
  if (!line) return;
  if (targetDutyPercent <= 0) {
    line.setValue(0);
    return;
  }
  line.setValue(1);
  if (targetDutyPercent >= 100) return;
  const offDelayMs = (1 - targetDutyPercent / 100) * PWM_PERIOD_MS;
  if (pwmTimeout) clearTimeout(pwmTimeout);
  pwmTimeout = setTimeout(() => {
    pwmTimeout = null;
    if (fanLine) fanLine.setValue(0);
  }, Math.max(0, Math.round(offDelayMs)));
}

function startPwm(): void {
  if (pwmInterval) return;
  pwmInterval = setInterval(pwmTick, PWM_PERIOD_MS);
}

function stopPwm(): void {
  if (pwmInterval) {
    clearInterval(pwmInterval);
    pwmInterval = null;
  }
  if (pwmTimeout) {
    clearTimeout(pwmTimeout);
    pwmTimeout = null;
  }
  if (fanLine) {
    try {
      fanLine.setValue(0);
    } catch {
      /* ignore */
    }
  }
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
    const { openGpioChip, Output } = require("easy-gpiod");
    const chip = openGpioChip("/dev/gpiochip0");
    const request = chip.requestLines("furbacca-fan", {
      fan: Output(FAN_BCM, { initial_value: false, final_value: false }),
    });
    const lineObj = request.lines.fan;
    // Wrap so we have setValue(0|1) and release() for cleanup
    const line: LineLike = {
      setValue(value: number) {
        lineObj.value = !!value;
      },
      release() {
        request.close();
      },
    };
    line.setValue(0); // Immediate: LOW so fans don't float
    fanChip = chip;
    fanRequest = request;
    fanLine = line;
    targetDutyPercent = 0;
    startPwm();
    initialized = true;

    const cleanup = (): void => {
      stopPwm();
      targetDutyPercent = 0;
      if (fanLine) {
        try {
          fanLine.setValue(0);
          if (typeof fanLine.release === "function") fanLine.release();
        } catch {
          /* ignore */
        }
        fanLine = null;
      }
      fanRequest = null;
      if (fanChip) {
        try {
          fanChip.close();
        } catch {
          /* ignore */
        }
        fanChip = null;
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
  } catch {
    // easy-gpiod not installed, or not on Pi, or gpiod not available
    fanChip = null;
    fanRequest = null;
    fanLine = null;
  }
}

/**
 * Ramp PWM from 0% to 100% over rampMs to avoid voltage brownout.
 * Call after init(); safe to call even if init() was no-op.
 */
export async function softStart(rampMs: number = SOFT_START_MS): Promise<void> {
  if (!fanLine || !initialized) return;

  const steps = 50;
  const stepMs = rampMs / steps;
  const dutyPerStep = 100 / steps;

  for (let i = 1; i <= steps; i++) {
    targetDutyPercent = Math.min(100, Math.round(dutyPerStep * i));
    await sleep(stepMs);
  }
  targetDutyPercent = 100;
}

/**
 * Set fan duty 0–100 (percent). Use after softStart for runtime control.
 */
export function setSpeed(percent: number): void {
  if (!initialized) return;
  targetDutyPercent = Math.max(0, Math.min(100, Math.round(percent)));
}

export const fanControl = { init, softStart, setSpeed };
