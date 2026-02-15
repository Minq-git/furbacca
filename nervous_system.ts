import { execSync, spawn } from "child_process";
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

const tableTitle = "+--------------+ Furbacca Hardware Status +--------------+";
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

/** If set (e.g. 0x60), belly touch runs chip-tool onoff on <nodeId> <endpoint>. Requires chip-tool (e.g. sudo snap install chip-tool). */
const chipToolNodeId = process.env.CHIP_TOOL_NODE_ID?.trim() || undefined;
const chipToolEndpoint = process.env.CHIP_TOOL_ENDPOINT ?? "0x1";

async function startMatterIfEnabled(): Promise<string[] | undefined> {
  if (!matterEnabled) {
    console.log("  🧠 Matter: disabled (FURBACCA_MATTER=0). Remove it or set FURBACCA_MATTER=1 to enable.");
    return undefined;
  }
  const matterLogBuffer: string[] = [];
  const { MatterLobe } = await import("./vision/ts/matter_lobe.js");
  const matter = new MatterLobe(eyes, touch);
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

console.log("+------+ Furbacca Nervous System: Modular Edition +------+");
console.log(`  👀 Eyes: listening at ${visionHost}:5005.`);
if (matterEnabled) console.log("  🧠 Matter Lobe: enabled (Furbacca as light + switches).");
if (chipToolNodeId) console.log(`  💡 chip-tool: belly touch → onoff on ${chipToolNodeId} ${chipToolEndpoint}`);
if (!headHw.ok && headHw.message) console.log(`  Head touch: ${headHw.message}`);
if (!bellyHw.ok && bellyHw.message) console.log(`  Belly touch: ${bellyHw.message}`);
if (!vibeHw.ok && vibeHw.message) console.log(`  Vibration: ${vibeHw.message}`);

let headActive = false;
let bellyActive = false;

function handleBellyTouch(): void {
  console.log("  🐾 Belly: cycling species");
  eyes.cycleEyeType();
  eyes.sendCommand("look", { x: 0, y: 0, pupil_mode: "wide" });
  chipToolOn();
}

function onTouch(sensor: "head" | "belly" | "shiver", active: boolean): void {
  if (sensor === "head") headActive = active;
  else if (sensor === "belly") bellyActive = active;

  if (!active) return;
  if (sensor === "head") {
    console.log("  🐾 Head: touch");
    eyes.blink();
    eyes.playAnimation("nervous_look", { replace: true });
  } else if (sensor === "belly") {
    handleBellyTouch();
  } else if (sensor === "shiver") {
    console.log(`  🫨  Shiver: BCM ${VIBE_BCM}`);
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
        console.log("+----------+ Furbacca Matter Startup Logs +----------+");
        matterLogBuffer.forEach((line) => console.log(line));
      }
      console.log(sep);
    }
  }, stepMs);
}

const MATTER_LOBE_STATUS_LINES = [
  "Initializing (single stack 0.12)...",
  "Checking UDP port 5540 ...",
  "Port free. Creating ServerNode (this may take a minute)...",
  "Node created. Adding endpoints...",
  "Endpoints ready. Starting node...",
  "Online. Pairing code and QR above.",
];

// Prefer event-driven (gpiomon) for minimal latency; fall back to 20ms polling
const stopEventWatch = touch.startEventWatch(onTouch);
if (stopEventWatch) {
  console.log("  🫳  Touch: event-driven (gpiomon).");
  if (matterEnabled) MATTER_LOBE_STATUS_LINES.forEach((msg) => console.log("  🧠 Matter Lobe: " + msg));
  process.on("SIGINT", () => {
    eyes.closeEyes();
    stopEventWatch();
    process.exit(0);
  });
  startMatterIfEnabled().then((buffer) => startWarmupThenOpen(buffer));
} else {
  console.log("  ⏳ Touch: polling every 20ms (install gpiomon for event-driven)");
  if (matterEnabled) MATTER_LOBE_STATUS_LINES.forEach((msg) => console.log("  🧠 Matter Lobe: " + msg));
  setInterval(() => touch.poll(onTouch), 20);
  startMatterIfEnabled().then((buffer) => startWarmupThenOpen(buffer));
}
