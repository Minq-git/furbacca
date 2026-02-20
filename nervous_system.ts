import { execSync, spawn } from "child_process";
import * as dgram from "dgram";
import fs from "fs";
import path from "path";
import { fanControl } from "./cooling/fan_control.js";
import { msg, substitute } from "./messages.js";
import { monitorMotion } from "./senses/motion.js";
import { initAudio, playGiggle } from "./sounds/ts/audio.js";
import { TouchSenses, VIBE_BCM } from "./senses/touch";
import { EyeBridge } from "./vision/ts/eye_bridge";

// First: prevent fan from floating (BCM 24 LOW) before any other GPIO or heavy work
fanControl.init();

function loadWarmupConfig(): {
  EYE_WARMUP_STEPS: number;
  WARMUP_MS: number;
  WARMUP_BEIGE: [number, number, number];
  WARMUP_GREEN: [number, number, number];
  STATUS_FAIL_RED: [number, number, number];
  OPEN_THEN_LOOK_MS: number;
  MOTION_SLEEP_MS: number;
  MOTION_CLEAR_DEBOUNCE_MS: number;
  SLEEP_CLOSE_DURATION_S: number;
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
  OPEN_THEN_LOOK_MS,
  MOTION_SLEEP_MS,
  MOTION_CLEAR_DEBOUNCE_MS,
  SLEEP_CLOSE_DURATION_S,
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
const fanState = (): StatusState => {
  if (process.env.FURBACCA_FAN === "0" || process.env.FURBACCA_FAN === "false") return "unknown";
  if (process.platform !== "linux") return "unknown";
  return fanControl.isInitialized() ? "ok" : "fail";
};
const voiceState = (): StatusState => {
  if (process.platform !== "linux") return "unknown";
  try {
    execSync("which aplay", { stdio: "ignore" });
    return "ok";
  } catch {
    return "fail";
  }
};

const rows: string[] = [
  "| GC9A01PY    | Left Eye            | 8        | " + statusCell(displayState()) + " |",
  "| GC9A01PY    | Right Eye           | 7        | " + statusCell(displayState()) + " |",
  "| TTP223B     | Head Touch          | 17       | " + statusCell(headState()) + " |",
  "| TTP223B     | Belly Touch         | 22       | " + statusCell(bellyState()) + " |",
  "| SW-420      | Vibration (Shiver)  | 23       | " + statusCell(vibeState()) + " |",
  "| MAX98357A   | Voice (I2S)         | 18,19,21 | " + statusCell(voiceState()) + " |",
  "| Cooling     | Fan (BCM 24)        | 24       | " + statusCell(fanState()) + " |",
];

/**
 * Warmup spinner = progress indicator for the ENTIRE startup when the user only has the device (no terminal/SSH).
 * Each step advances the spinner on the eyes (beige → green); labels below are for the terminal bar.
 * Someone in front of Furbacca sees the eyes fill from brown to green as each phase completes.
 */
const WARMUP_STEP_LABELS: string[] = [
  "Hardware ready",
  "NS / Voice",
  "Touch arming",
  "Motion arming",
  "Status",
  "Matter starting",
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

const CLEAR_LINE = "\x1b[K";

const touch = new TouchSenses(0);
const eyes = new EyeBridge();

/** Advance spinner to step (terminal bar + eyes). Call at each setup phase so the eyes show progress to someone watching the device. */
function advanceWarmup(step: number): void {
  const label = WARMUP_STEP_LABELS[step] ?? "Starting";
  if (step === 0) {
    process.stdout.write(warmupBar(0, WARMUP_STEPS, label) + "\n");
  } else {
    process.stdout.write("\r" + CLEAR_LINE + warmupBar(step, WARMUP_STEPS, label));
  }
  eyes.warmup(step);
}

/** Eyes subprocess: we spawn and restart on exit so they recover during heavy Matter init. */
let eyesChild: ReturnType<typeof spawn> | null = null;
let isShuttingDown = false;
const EYES_RESTART_DELAY_MS = 2000;

/** Buffer eyes output until warmup bar is done so logs don't interleave with the progress line. */
const eyesOutputBuffer: string[] = [];
let eyesOutputBuffered = true;

function forwardWithPrefix(stream: NodeJS.ReadableStream, prefix: string): void {
  stream.setEncoding("utf8");
  stream.on("data", (chunk: string) => {
    const lines = String(chunk).split(/\r?\n/).filter(Boolean);
    for (const line of lines) {
      const out = prefix + line + "\n";
      if (eyesOutputBuffered) eyesOutputBuffer.push(out);
      else process.stderr.write(out);
    }
  });
}

function flushEyesBuffer(): void {
  eyesOutputBuffered = false;
  for (const line of eyesOutputBuffer) process.stderr.write(line);
  eyesOutputBuffer.length = 0;
}

function startEyesProcess(): void {
  const repoRoot = process.cwd();
  const scriptPath = path.join(repoRoot, "vision", "py", "eyes.py");
  const venvPython = path.join(repoRoot, "env", "bin", "python3");
  const pythonPath = fs.existsSync(venvPython) ? venvPython : "python3";
  eyesChild = spawn(pythonPath, [scriptPath], {
    cwd: repoRoot,
    env: { ...process.env, PYTHONUNBUFFERED: "1", UDP_BIND: "0.0.0.0" },
    stdio: ["ignore", "pipe", "pipe"],
  });
  if (eyesChild.stdout) forwardWithPrefix(eyesChild.stdout, "");
  if (eyesChild.stderr) forwardWithPrefix(eyesChild.stderr, "");
  eyesChild.on("exit", (code, signal) => {
    eyesChild = null;
    if (isShuttingDown) return;
    console.log(msg.nervous_system.eyes_restarted);
    setTimeout(() => startEyesProcess(), EYES_RESTART_DELAY_MS);
  });
}

// Start eyes first so they bind while we print the table; spinner shows on displays as early as possible
startEyesProcess();

const tableTitle = msg.nervous_system.hardware_table_title;
console.log(tableTitle);
console.log(sep);
console.log(header);
console.log(sep);
for (const row of rows) {
  console.log(row);
}
console.log(sep);

// Give eyes time to bind, init displays, and enter main loop so spinner shows from step 0 (device-only progress)
if (process.platform === "linux") {
  try {
    execSync("sleep 1.2", { stdio: "ignore" });
  } catch {
    /* ignore */
  }
}
advanceWarmup(0); // Hardware ready; spinner visible during rest of startup

/** Matter Lobe is on by default. Set FURBACCA_MATTER=0 (or false) to disable for troubleshooting. Requires 64-bit Node on Pi. */
const matterEnabled = process.env.FURBACCA_MATTER !== "0" && process.env.FURBACCA_MATTER !== "false";

/** Set when Matter starts; used to forward touch to Matter and to close on SIGINT. */
let matterLobe: { notifyTouch(sensor: "head" | "belly" | "shiver", active: boolean): void; close(): Promise<void> } | null = null;

/** If set (e.g. 0x60), belly touch runs chip-tool onoff on <nodeId> <endpoint>. Requires chip-tool (e.g. sudo snap install chip-tool). */
const chipToolNodeId = process.env.CHIP_TOOL_NODE_ID?.trim() || undefined;
const chipToolEndpoint = process.env.CHIP_TOOL_ENDPOINT ?? "0x1";

// Same as Matter Lobe: repo .matter so fabric/CASE and pairing cache persist in one place
const MATTER_DIR = path.join(process.cwd(), ".matter");
const PAIRING_DISPLAY_CACHE = path.join(MATTER_DIR, "pairing_display.txt");
const PAIRING_QR_PATTERN =
  /Commissioning|passcode|discriminator|pairing|uncommissioned|qrcode|QR code|manual pairing|▄|▀|█|project-chip\.github\.io/i;

/** Result when Matter is enabled: buffer + whether we already printed pairing block and sep. */
type MatterStartResult = { buffer: string[]; showedCachedPairing: boolean };

async function startMatterIfEnabled(): Promise<MatterStartResult | undefined> {
  if (!matterEnabled) {
    console.log(msg.nervous_system.matter_disabled);
    return undefined;
  }
  let showedCachedPairing = false;
  if (fs.existsSync(PAIRING_DISPLAY_CACHE)) {
    try {
      const cached = fs.readFileSync(PAIRING_DISPLAY_CACHE, "utf-8").trim();
      if (cached) {
        console.log(msg.nervous_system.matter_startup_logs_header);
        console.log(cached);
        console.log(sep);
        showedCachedPairing = true;
      }
    } catch {
      /* ignore read errors */
    }
  }
  const matterLogBuffer: string[] = [];
  const { MatterLobe } = await import("./brain/ts/matter_lobe.js");
  const matter = new MatterLobe(eyes, touch);
  matterLobe = matter;
  try {
    await matter.start({
      onStatus: () => {},
      matterLogBuffer,
      pairingAlreadyShown: showedCachedPairing,
    });
  } catch (e) {
    console.error(e);
  }
  if (showedCachedPairing) {
    for (let i = matterLogBuffer.length - 1; i >= 0; i--) {
      if (PAIRING_QR_PATTERN.test(matterLogBuffer[i]!)) matterLogBuffer.splice(i, 1);
    }
  } else {
    const pairingLines = matterLogBuffer.filter((line) => PAIRING_QR_PATTERN.test(line));
    if (pairingLines.length > 0) {
      try {
        fs.mkdirSync(MATTER_DIR, { recursive: true });
        fs.writeFileSync(PAIRING_DISPLAY_CACHE, pairingLines.join("\n"), "utf-8");
      } catch {
        /* ignore write errors */
      }
    }
  }
  return { buffer: matterLogBuffer, showedCachedPairing };
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

/** UDP port for local events (e.g. eye-track.sh notifies when tracking starts/stops). */
const NS_EVENTS_PORT = 5006;
const nsEventsSocket = dgram.createSocket("udp4");
nsEventsSocket.bind(NS_EVENTS_PORT, "127.0.0.1", () => {
  nsEventsSocket.on("message", (buf: Buffer) => {
    try {
      const payload = JSON.parse(buf.toString()) as { event?: string };
      if (payload.event === "eye_tracking_started") console.log(msg.nervous_system.eye_tracking_started);
      else if (payload.event === "eye_tracking_stopped") console.log(msg.nervous_system.eye_tracking_stopped);
      else if (payload.event === "looking_started") console.log(msg.nervous_system.looking_started);
      else if (payload.event === "looking_stopped") console.log(msg.nervous_system.looking_stopped);
    } catch {
      /* ignore malformed */
    }
  });
});

console.log(msg.nervous_system.header);
console.log(substitute(msg.nervous_system.eyes_listening, { host: visionHost }));
console.log(substitute(msg.nervous_system.voice_ready, { card: process.env.FURBACCA_AUDIO_CARD ?? "0" }));
if (process.platform === "linux" && (process.env.FURBACCA_EYE_TRACK ?? "1") !== "0") {
  console.log(msg.nervous_system.eye_tracker_starting);
}
initAudio(); // volume/no-control message once at startup so first head touch only logs "Playing giggle"
if (matterEnabled) console.log(msg.nervous_system.matter_lobe_enabled);
if (chipToolNodeId) console.log(substitute(msg.nervous_system.chip_tool_belly, { nodeId: chipToolNodeId, endpoint: chipToolEndpoint }));
if (!headHw.ok && headHw.message) console.log(substitute(msg.nervous_system.head_touch_error, { message: headHw.message }));
if (!bellyHw.ok && bellyHw.message) console.log(substitute(msg.nervous_system.belly_touch_error, { message: bellyHw.message }));
if (!vibeHw.ok && vibeHw.message) console.log(substitute(msg.nervous_system.vibration_error, { message: vibeHw.message }));

advanceWarmup(1); // NS / Voice

let headActive = false;
let bellyActive = false;

/** Head + belly: 5s = eyes re-init, 30s = network heal script (long to avoid accidental trigger). */
const HEAD_BELLY_HOLD_MS = 5000;
const NETWORK_HEAL_HOLD_MS = 30000;
let headBellyHoldTimer: ReturnType<typeof setTimeout> | null = null;
let networkHealTimer: ReturnType<typeof setTimeout> | null = null;
let headBellyHoldCooldown = false;

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

  // Head + belly: 5s → eyes re-init; 30s → network heal script
  if (sensor === "head" || sensor === "belly") {
    if (!headActive || !bellyActive) {
      if (headBellyHoldTimer !== null) {
        clearTimeout(headBellyHoldTimer);
        headBellyHoldTimer = null;
      }
      if (networkHealTimer !== null) {
        clearTimeout(networkHealTimer);
        networkHealTimer = null;
      }
      if (!headActive && !bellyActive) headBellyHoldCooldown = false;
    } else if (!headBellyHoldCooldown) {
      headBellyHoldCooldown = true;
      headBellyHoldTimer = setTimeout(() => {
        headBellyHoldTimer = null;
        console.log(msg.nervous_system.eyes_full_reinit_trigger);
        eyes.sendCommand("restart_both", {});
        eyes.playAnimation("nervous_look", { replace: true });
      }, HEAD_BELLY_HOLD_MS);
      networkHealTimer = setTimeout(() => {
        networkHealTimer = null;
        console.log(msg.nervous_system.network_heal_trigger);
        eyes.sendCommand("set_eye_type", { type: "demon" });
        const scriptPath = path.join(process.cwd(), "scripts", "heal-network.sh");
        const child = spawn("bash", [scriptPath], { detached: true, stdio: "ignore" });
        child.unref();
      }, NETWORK_HEAL_HOLD_MS);
    }
  }

  if (!active) return;
  if (sensor === "head") {
    console.log(msg.nervous_system.head_touch);
    eyes.blink();
    eyes.playAnimation("nervous_look", { replace: true });
    console.log(msg.audio.giggle_playing);
    playGiggle();
  } else if (sensor === "belly") {
    handleBellyTouch();
  } else if (sensor === "shiver") {
    console.log(substitute(msg.nervous_system.shiver, { bcm: String(VIBE_BCM) }));
    eyes.impulse();
  }
}

/** Runs final warmup steps (6, 7) then opens eyes; Matter logs printed when promise resolves. */
function startWarmupThenOpen(matterResultPromise: Promise<MatterStartResult | undefined>): void {
  advanceWarmup(6); // Preparing eyes…
  advanceWarmup(7); // Ready (full green)
  flushEyesBuffer();
  process.stdout.write("\r" + CLEAR_LINE + warmupBar(WARMUP_STEPS, WARMUP_STEPS, "Opening eyes.") + "\n");
  warmupComplete = true;
  if (motionFirstDetectedPendingLog) {
    motionFirstDetectedPendingLog = false;
    motionFirstDetectedLogged = true;
    console.log("  👁  Motion: sensor triggered (Furbacca will say \"noticed someone!\" when waking from sleep).");
  }
  eyes.openEyes();
  matterResultPromise.then((result) => {
    if (result?.buffer?.length) {
      console.log(msg.nervous_system.matter_startup_logs_header);
      result.buffer.forEach((line) => console.log(line));
    }
    if (!result?.showedCachedPairing) console.log(sep);
    // Re-trigger eyes after Matter finishes (shared RST/SPI can leave one panel black; openEyes redraws)
    eyes.openEyes();
    setTimeout(() => eyes.playAnimation("nervous_look", { replace: true }), 800);
  });
}

const matterLobeStatus = msg.matter_lobe.status as Record<string, string>;

// Prefer event-driven (gpiomon) for minimal latency; fall back to 20ms polling
const stopEventWatch = touch.startEventWatch(onTouch);
advanceWarmup(2); // Touch arming
const stopMotionWatch = monitorMotion(onMotion);
advanceWarmup(3); // Motion arming

let motionSleepTimer: ReturnType<typeof setTimeout> | null = null;
/** Debounce: only start sleep timer after no motion for MOTION_CLEAR_DEBOUNCE_MS. */
let motionClearDebounceTimer: ReturnType<typeof setTimeout> | null = null;
/** True after warmup finishes and eyes.openEyes() has been called; don't trigger sleep during warmup. */
let warmupComplete = false;
/** True when we've gone to sleep (no motion for 2 min); we only play nervous_look when waking from this. */
let motionWasAsleep = false;
/** Log once when motion is first detected so user knows the sensor is firing (reaction only when waking from sleep). */
let motionFirstDetectedLogged = false;
/** Set when motion fires during warmup; log after warmup bar is done so it doesn't interleave. */
let motionFirstDetectedPendingLog = false;

function onMotion(detected: boolean): void {
  if (detected) {
    if (!motionFirstDetectedLogged) {
      if (warmupComplete) {
        motionFirstDetectedLogged = true;
        console.log("  👁  Motion: sensor triggered (Furbacca will say \"noticed someone!\" when waking from sleep).");
      } else {
        motionFirstDetectedPendingLog = true;
      }
    }
    if (motionClearDebounceTimer !== null) {
      clearTimeout(motionClearDebounceTimer);
      motionClearDebounceTimer = null;
    }
    if (motionSleepTimer !== null) {
      clearTimeout(motionSleepTimer);
      motionSleepTimer = null;
    }
    if (motionWasAsleep) {
      motionWasAsleep = false;
      console.log(msg.nervous_system.motion_detected);
      eyes.openEyes();
      setTimeout(() => eyes.playAnimation("nervous_look", { replace: true }), OPEN_THEN_LOOK_MS);
    }
  } else {
    if (motionClearDebounceTimer !== null) clearTimeout(motionClearDebounceTimer);
    motionClearDebounceTimer = setTimeout(() => {
      motionClearDebounceTimer = null;
      if (motionSleepTimer !== null) clearTimeout(motionSleepTimer);
      if (!warmupComplete) return;
      motionSleepTimer = setTimeout(() => {
        motionSleepTimer = null;
        motionWasAsleep = true;
        eyes.sleepClose(SLEEP_CLOSE_DURATION_S);
        console.log(msg.nervous_system.motion_sleep);
      }, MOTION_SLEEP_MS);
    }, MOTION_CLEAR_DEBOUNCE_MS);
  }
}

async function onShutdown(): Promise<void> {
  if (motionClearDebounceTimer !== null) {
    clearTimeout(motionClearDebounceTimer);
    motionClearDebounceTimer = null;
  }
  if (motionSleepTimer !== null) {
    clearTimeout(motionSleepTimer);
    motionSleepTimer = null;
  }
  isShuttingDown = true;
  if (eyesChild) {
    eyesChild.kill("SIGTERM");
    eyesChild = null;
  }
  eyes.closeEyes();
  await matterLobe?.close(); // Flush Matter storage and announce shutdown via mDNS
  const stopMotion = stopMotionWatch ? stopMotionWatch() : Promise.resolve();
  const stopTouch = stopEventWatch ? stopEventWatch() : Promise.resolve();
  await Promise.all([stopMotion, stopTouch]);
  process.exit(0);
}
process.on("SIGINT", () => void onShutdown());

// Group touch + Matter Lobe status lines, then start Matter (cached pairing prints right after if present)
const hasCachedPairing = matterEnabled && fs.existsSync(PAIRING_DISPLAY_CACHE);
const matterLobeStatusLines = msg.matter_lobe.status_order.map((key) => {
  if (key === "checking_port") return substitute(matterLobeStatus[key], { port: "5540" });
  if (key === "online" && hasCachedPairing) return matterLobeStatus.online_short ?? "Online.";
  return matterLobeStatus[key];
});

if (stopEventWatch) {
  console.log(msg.nervous_system.touch_event_driven);
  if (matterEnabled) {
    matterLobeStatusLines.forEach((line) => console.log(msg.nervous_system.matter_lobe_prefix + line));
    console.log(
      msg.nervous_system.matter_lobe_prefix + `Storage: ${path.join(process.cwd(), ".matter")} (cwd: ${process.cwd()})`
    );
  }
} else {
  console.log(msg.nervous_system.touch_polling);
  if (matterEnabled) {
    matterLobeStatusLines.forEach((line) => console.log(msg.nervous_system.matter_lobe_prefix + line));
    console.log(
      msg.nervous_system.matter_lobe_prefix + `Storage: ${path.join(process.cwd(), ".matter")} (cwd: ${process.cwd()})`
    );
  }
}
if (stopMotionWatch) {
  console.log(msg.nervous_system.motion_event_driven);
  console.log(msg.nervous_system.motion_sensor_enabled);
}

advanceWarmup(4); // Status
advanceWarmup(5); // Matter starting

// Matter and warmup run in parallel; eyes open when warmup finishes, Matter logs when Matter finishes
const matterPromise = matterEnabled
  ? startMatterIfEnabled()
  : (console.log(msg.nervous_system.matter_disabled), Promise.resolve(undefined));

if (stopEventWatch) {
  void fanControl.softStart().then(() => fanControl.startThermalWatchdog()); // ramp then thermal-based speed
  startWarmupThenOpen(matterPromise);
} else {
  void fanControl.softStart().then(() => fanControl.startThermalWatchdog());
  setInterval(() => touch.poll(onTouch), 20);
  startWarmupThenOpen(matterPromise);
}
