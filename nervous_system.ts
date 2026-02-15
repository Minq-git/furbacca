import { execSync, spawn } from "child_process";
import fs from "fs";
import path from "path";
import { msg, substitute } from "./messages.js";
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

const sep = msg.nervous_system.hardware_table_sep;
const header = msg.nervous_system.hardware_table_header;
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

const tableTitle = msg.nervous_system.hardware_table_title;
console.log(tableTitle);
console.log(sep);
console.log(header);
console.log(sep);
for (const row of rows) {
  console.log(row);
}
console.log(sep);

const touch = new TouchSenses(0);
const eyes = new EyeBridge();

/** Matter Lobe is on by default. Set FURBACCA_MATTER=0 (or false) to disable for troubleshooting. Requires 64-bit Node on Pi. */
const matterEnabled = process.env.FURBACCA_MATTER !== "0" && process.env.FURBACCA_MATTER !== "false";

/** Set when Matter starts; used to forward touch to Matter and to close on SIGINT. */
let matterLobe: { notifyTouch(sensor: "head" | "belly" | "shiver", active: boolean): void; close(): void } | null = null;

/** If set (e.g. 0x60), belly touch runs chip-tool onoff on <nodeId> <endpoint>. Requires chip-tool (e.g. sudo snap install chip-tool). */
const chipToolNodeId = process.env.CHIP_TOOL_NODE_ID?.trim() || undefined;
const chipToolEndpoint = process.env.CHIP_TOOL_ENDPOINT ?? "0x1";

async function startMatterIfEnabled(): Promise<string[] | undefined> {
  if (!matterEnabled) {
    console.log(msg.nervous_system.matter_disabled);
    return undefined;
  }
  const matterLogBuffer: string[] = [];
  const { MatterLobe } = await import("./vision/ts/matter_lobe.js");
  const matter = new MatterLobe(eyes, touch);
  matterLobe = matter;
  try {
    await matter.start({ onStatus: () => {}, matterLogBuffer });
  } catch (e) {
    console.error(e);
  }
  return matterLogBuffer;
}

function chipToolOn(): void {
  if (!chipToolNodeId) return;
  const child = spawn("chip-tool", ["onoff", "on", chipToolNodeId, chipToolEndpoint], {
    stdio: "ignore",
    detached: true,
  });
  child.unref();
}

const visionHost = process.env.VISION_HOST ?? "127.0.0.1";

console.log(msg.nervous_system.header);
console.log(substitute(msg.nervous_system.eyes_listening, { host: visionHost }));
if (matterEnabled) console.log(msg.nervous_system.matter_lobe_enabled);
if (chipToolNodeId) console.log(substitute(msg.nervous_system.chip_tool_belly, { nodeId: chipToolNodeId, endpoint: chipToolEndpoint }));
if (!headHw.ok && headHw.message) console.log(substitute(msg.nervous_system.head_touch_error, { message: headHw.message }));
if (!bellyHw.ok && bellyHw.message) console.log(substitute(msg.nervous_system.belly_touch_error, { message: bellyHw.message }));
if (!vibeHw.ok && vibeHw.message) console.log(substitute(msg.nervous_system.vibration_error, { message: vibeHw.message }));

let headActive = false;
let bellyActive = false;

function handleBellyTouch(): void {
  console.log(msg.nervous_system.belly_cycling);
  eyes.cycleEyeType();
  eyes.sendCommand("look", { x: 0, y: 0, pupil_mode: "wide" });
  chipToolOn();
}

function onTouch(sensor: "head" | "belly" | "shiver", active: boolean): void {
  if (sensor === "head") headActive = active;
  else if (sensor === "belly") bellyActive = active;

  matterLobe?.notifyTouch(sensor, active);

  if (!active) return;
  if (sensor === "head") {
    console.log(msg.nervous_system.head_touch);
    eyes.blink();
    eyes.playAnimation("nervous_look", { replace: true });
  } else if (sensor === "belly") {
    handleBellyTouch();
  } else if (sensor === "shiver") {
    console.log(substitute(msg.nervous_system.shiver, { bcm: String(VIBE_BCM) }));
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

function startWarmupThenOpen(matterLogBuffer?: string[]): void {
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
      if (matterLogBuffer?.length) {
        console.log(msg.nervous_system.matter_startup_logs_header);
        matterLogBuffer.forEach((line) => console.log(line));
      }
      console.log(sep);
    }
  }, stepMs);
}

const matterLobeStatus = msg.matter_lobe.status as Record<string, string>;
const MATTER_LOBE_STATUS_LINES = msg.matter_lobe.status_order.map((key) =>
  key === "checking_port" ? substitute(matterLobeStatus[key], { port: "5540" }) : matterLobeStatus[key]
);

// Prefer event-driven (gpiomon) for minimal latency; fall back to 20ms polling
const stopEventWatch = touch.startEventWatch(onTouch);
function onShutdown(): void {
  eyes.closeEyes();
  matterLobe?.close();
  if (stopEventWatch) {
    stopEventWatch().then(() => process.exit(0));
  } else {
    process.exit(0);
  }
}
process.on("SIGINT", () => onShutdown());

if (stopEventWatch) {
  console.log(msg.nervous_system.touch_event_driven);
  if (matterEnabled) MATTER_LOBE_STATUS_LINES.forEach((line) => console.log(msg.nervous_system.matter_lobe_prefix + line));
  startMatterIfEnabled().then((buffer) => startWarmupThenOpen(buffer));
} else {
  console.log(msg.nervous_system.touch_polling);
  if (matterEnabled) MATTER_LOBE_STATUS_LINES.forEach((line) => console.log(msg.nervous_system.matter_lobe_prefix + line));
  setInterval(() => touch.poll(onTouch), 20);
  startMatterIfEnabled().then((buffer) => startWarmupThenOpen(buffer));
}
