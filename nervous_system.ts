import { execSync } from "child_process";
import fs from "fs";
import path from "path";
import { TouchSenses, VIBE_BCM } from "./senses/touch";
import { EyeBridge } from "./vision/ts/eye_bridge";

function loadWarmupConfig(): {
  EYE_WARMUP_STEPS: number;
  WARMUP_MS: number;
  WARMUP_BEIGE: [number, number, number];
  WARMUP_GREEN: [number, number, number];
  STATUS_FAIL_RED: [number, number, number];
} {
  const repoRoot = process.cwd();
  const scriptPath = path.join(repoRoot, "vision", "py", "export_warmup_config.py");
  const out = execSync(`python3 "${scriptPath}"`, { encoding: "utf-8", cwd: repoRoot });
  return JSON.parse(out);
}

const {
  EYE_WARMUP_STEPS: WARMUP_STEPS,
  WARMUP_MS,
  WARMUP_BEIGE,
  WARMUP_GREEN,
  STATUS_FAIL_RED,
} = loadWarmupConfig();

const ANSI_RESET = "\x1b[0m";
function ansiRgb(r: number, g: number, b: number): string {
  return `\x1b[38;2;${r};${g};${b}m`;
}

function readDisplayStatus(): "ok" | "fail" | "unknown" {
  const filePath = path.join(process.cwd(), ".furbacca-hardware.json");
  for (let i = 0; i < 2; i++) {
    try {
      if (fs.existsSync(filePath)) {
        const data = JSON.parse(fs.readFileSync(filePath, "utf-8")) as { displays?: string };
        return data.displays === "ok" ? "ok" : data.displays === "fail" ? "fail" : "unknown";
      }
    } catch {
      /* ignore */
    }
    if (i === 0 && process.platform === "linux") {
      try {
        execSync("sleep 1.5", { stdio: "ignore" });
      } catch {
        break;
      }
    }
  }
  return "unknown";
}

const displayStatus = readDisplayStatus();
const headHw = TouchSenses.checkHeadTouch(0);
const bellyHw = TouchSenses.checkBellyTouch(0);
const vibeHw = TouchSenses.checkVibration(0);

type StatusState = "unknown" | "ok" | "fail";

function statusCell(state: StatusState): string {
  const [r, g, b] =
    state === "ok"
      ? WARMUP_GREEN
      : state === "fail"
        ? STATUS_FAIL_RED
        : WARMUP_BEIGE;
  const char = state === "unknown" ? "--" : state === "ok" ? "✓" : "✕";
  const padLeft = state === "unknown" ? "   " : "   ";
  const padRight = state === "unknown" ? "   " : "   ";
  return padLeft + ansiRgb(r, g, b) + char + ANSI_RESET + padRight;
}

const sep = "+-------------+---------------------+----------+---------+";
const header = "| Module Name | Position            | Pin      | Status  |";
const displayState = (): StatusState =>
  displayStatus === "unknown" ? "unknown" : displayStatus === "ok" ? "ok" : "fail";
const headState = (): StatusState =>
  process.platform !== "linux" ? "unknown" : headHw.ok ? "ok" : "fail";
const bellyState = (): StatusState =>
  process.platform !== "linux" ? "unknown" : bellyHw.ok ? "ok" : "fail";
const vibeState = (): StatusState =>
  process.platform !== "linux" ? "unknown" : vibeHw.ok ? "ok" : "fail";

const rows: string[] = [
  "| GC9A01PY    | Left Eye            | BCM 8    | " + statusCell(displayState()) + " |",
  "| GC9A01PY    | Right Eye           | BCM 7    | " + statusCell(displayState()) + " |",
  "| TTP223B     | Head Touch          | BCM 17   | " + statusCell(headState()) + " |",
  "| TTP223B     | Belly Touch         | BCM 22   | " + statusCell(bellyState()) + " |",
  "| SW-420      | Vibration (Shiver)  | BCM 23   | " + statusCell(vibeState()) + " |",
];

console.log("Initializing nervous system...");
console.log(sep);
console.log(header);
console.log(sep);
for (const row of rows) {
  console.log(row);
}
console.log(sep);

const touch = new TouchSenses(0);
const eyes = new EyeBridge();

const visionHost = process.env.VISION_HOST ?? "127.0.0.1";

console.log("+------+ Furbacca Nervous System: Modular Edition +------+");
console.log(`  👀 Eyes: listening at ${visionHost}:5005.`);
if (!headHw.ok && headHw.message) console.log(`  Head touch: ${headHw.message}`);
if (!bellyHw.ok && bellyHw.message) console.log(`  Belly touch: ${bellyHw.message}`);
if (!vibeHw.ok && vibeHw.message) console.log(`  Vibration: ${vibeHw.message}`);

let headActive = false;
let bellyActive = false;

function handleBellyTouch(): void {
  console.log("🐾 Belly touch: Cycling species");
  eyes.cycleEyeType();
  eyes.sendCommand("look", { x: 0, y: 0, pupil_mode: "wide" });
}

function onTouch(sensor: "head" | "belly" | "shiver", active: boolean): void {
  if (sensor === "head") headActive = active;
  else if (sensor === "belly") bellyActive = active;

  if (!active) return;
  if (sensor === "head") {
    console.log("🐾 Head touch");
    eyes.blink();
    eyes.playAnimation("nervous_look", { replace: true });
  } else if (sensor === "belly") {
    handleBellyTouch();
  } else if (sensor === "shiver") {
    console.log(`🫨  SHIVER: BCM ${VIBE_BCM} detected vibration (Logic 0)`);
    eyes.impulse();
  }
}

const WARMUP_STEP_LABELS: string[] = [
  "Eyes waiting for nervous system",
  "Touch sensors initializing",
  "Eye bridge connecting",
  "Sensors arming",
  "Waking up…",
  "Almost there…",
  "Preparing eyes…",
  "Ready",
];

function warmupSegmentColor(blend: number): [number, number, number] {
  return [
    Math.round(WARMUP_BEIGE[0] * (1 - blend) + WARMUP_GREEN[0] * blend),
    Math.round(WARMUP_BEIGE[1] * (1 - blend) + WARMUP_GREEN[1] * blend),
    Math.round(WARMUP_BEIGE[2] * (1 - blend) + WARMUP_GREEN[2] * blend),
  ];
}

function warmupBar(filled: number, total: number, label: string): string {
  const pct = total > 0 ? Math.round((filled / total) * 100) : 0;
  let bar = "[";
  for (let i = 0; i < total; i++) {
    if (i < filled) {
      const blend = total > 1 ? i / (total - 1) : 0;
      const [r, g, b] = warmupSegmentColor(blend);
      bar += ansiRgb(r, g, b) + "█" + ANSI_RESET;
    } else {
      bar += "░";
    }
  }
  bar += "]";
  return `  ${bar} (${pct}%): ${label}`;
}

const CLEAR_LINE = "\x1b[K"; // clear from cursor to end of line

function startWarmupThenOpen(): void {
  const stepMs = WARMUP_MS / WARMUP_STEPS;
  let step = 0;
  process.stdout.write(warmupBar(step, WARMUP_STEPS, WARMUP_STEP_LABELS[step] ?? "Starting"));
  eyes.warmup(step);
  const tick = setInterval(() => {
    step += 1;
    if (step < WARMUP_STEPS) {
      process.stdout.write("\r" + CLEAR_LINE + warmupBar(step, WARMUP_STEPS, WARMUP_STEP_LABELS[step] ?? "Starting"));
      eyes.warmup(step);
    } else {
      clearInterval(tick);
      process.stdout.write("\r" + CLEAR_LINE + warmupBar(WARMUP_STEPS, WARMUP_STEPS, "Opening eyes.") + "\n");
      eyes.openEyes();
      console.log(sep);
    }
  }, stepMs);
}

// Prefer event-driven (gpiomon) for minimal latency; fall back to 20ms polling
const stopEventWatch = touch.startEventWatch(onTouch);
if (stopEventWatch) {
  console.log("  🫳  Touch: event-driven (gpiomon).");
  startWarmupThenOpen();
  process.on("SIGINT", () => {
    eyes.closeEyes();
    stopEventWatch();
    process.exit(0);
  });
} else {
  console.log("  ⏳ Touch: polling every 20ms (install gpiomon for event-driven)");
  setInterval(() => touch.poll(onTouch), 20);
  startWarmupThenOpen();
}
