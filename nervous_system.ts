import { execSync } from "child_process";

// BCM GPIO 17 (physical pin 11) and 22 (physical pin 15)
const HEAD_TOUCH_GPIO = 17;
const BELLY_TOUCH_GPIO = 22;
const POLL_MS = 100;

// Pi 5 uses chip 4 for the 40-pin header; older Pi use chip 0.
// gpiod 2.x uses: gpioget -c <chip> <line>...
function detectChip(): number {
  let lastErr: Error | null = null;
  for (const chipNum of [4, 0]) {
    try {
      execSync(`gpioget -c ${chipNum} ${HEAD_TOUCH_GPIO} ${BELLY_TOUCH_GPIO}`, {
        stdio: "pipe",
        encoding: "utf-8",
      });
      return chipNum;
    } catch (err) {
      lastErr = err instanceof Error ? err : new Error(String(err));
    }
  }
  const msg = lastErr?.message ?? "unknown";
  throw new Error(
    `No GPIO chip found (tried gpiochip4 and gpiochip0). Install gpiod: sudo apt install gpiod. Last error: ${msg}`
  );
}

const chipNum = detectChip();

function parseLineValue(s: string): number {
  const v = s.includes("=") ? s.split("=")[1] : s;
  if (v === "active" || v === "1") return 1;
  if (v === "inactive" || v === "0") return 0;
  return Number(v);
}

function readPins(): [number, number] {
  // gpiod 2.x: gpioget -c <chip> [--numeric] <lines...>
  let out: string;
  try {
    out = execSync(`gpioget -c ${chipNum} --numeric ${HEAD_TOUCH_GPIO} ${BELLY_TOUCH_GPIO}`, {
      encoding: "utf-8",
    });
  } catch {
    out = execSync(`gpioget -c ${chipNum} ${HEAD_TOUCH_GPIO} ${BELLY_TOUCH_GPIO}`, {
      encoding: "utf-8",
    });
  }
  const parts = out.trim().split(/\s+/);
  return [parseLineValue(parts[0]), parseLineValue(parts[1])];
}

let [lastHead, lastBelly] = readPins();

const poll = () => {
  const [head, belly] = readPins();

  if (head !== lastHead) {
    lastHead = head;
    console.log(head ? "🐾 Head Pet Detected!" : "🐾 Head Pet Released.");
  }
  if (belly !== lastBelly) {
    lastBelly = belly;
    console.log(belly ? "Tickle Detected!" : "Tickle Released.");
  }
};

console.log("--- Furbacca Nervous System: Trixie Mode ---");
console.log(`Watching for touch events (gpiochip${chipNum} GPIO ${HEAD_TOUCH_GPIO} & ${BELLY_TOUCH_GPIO})...`);

setInterval(poll, POLL_MS);
