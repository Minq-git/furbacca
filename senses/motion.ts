/**
 * PIR motion sensor (e.g. AM312) on BCM 4.
 * Event-driven via gpiomon (same pattern as touch.ts). Active-high: rising = motion detected.
 */
import { execSync, spawn, ChildProcess } from "child_process";

const MOTION_BCM = 4; // BCM 4 (Physical Pin 7) — instruction.md §1.D
const EDGE_RISING = 1;
const EDGE_FALLING = 2;

export type MotionCallback = (detected: boolean) => void;

export function hasGpiomon(): boolean {
  try {
    execSync("which gpiomon", { encoding: "utf-8" });
    return true;
  } catch {
    return false;
  }
}

/**
 * Start PIR motion monitoring with gpiomon. Calls callback on each edge (rising = motion, falling = clear).
 * Returns a stop function that kills gpiomon and resolves when the process has exited (so GPIO is released).
 */
export function monitorMotion(callback: MotionCallback): (() => Promise<void>) | null {
  if (process.platform !== "linux") {
    return null;
  }
  if (!hasGpiomon()) {
    return null;
  }
  const proc = spawn(
    "gpiomon",
    ["-c", "0", "-F", "%o %e\n", "-e", "both", String(MOTION_BCM)],
    { stdio: ["ignore", "pipe", "pipe"] }
  );
  let lastDetected: boolean | null = null;
  let buffer = "";
  proc.stdout?.on("data", (chunk: Buffer) => {
    buffer += chunk.toString();
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      const parts = line.trim().split(/\s+/);
      if (parts.length >= 2) {
        const edge = parseInt(parts[1], 10);
        const detected = edge === EDGE_RISING;
        if (lastDetected !== detected) {
          lastDetected = detected;
          callback(detected);
        }
      }
    }
  });
  proc.stderr?.on("data", (d) => process.stderr.write(d));
  proc.on("error", () => {
    motionProcess = null;
  });
  proc.on("exit", () => {
    motionProcess = null;
  });
  let motionProcess: ChildProcess | null = proc;
  return () => {
    const p = motionProcess;
    motionProcess = null;
    if (!p) return Promise.resolve();
    return new Promise<void>((resolve) => {
      const done = () => {
        clearTimeout(t);
        resolve();
      };
      p.once("exit", done);
      p.kill("SIGTERM");
      const t = setTimeout(() => {
        p.removeListener("exit", done);
        try {
          p.kill("SIGKILL");
        } catch {
          /* already gone */
        }
        resolve();
      }, 2000);
    });
  };
}

export { MOTION_BCM };
