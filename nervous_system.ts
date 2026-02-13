import { TouchSenses, VIBE_BCM } from "./senses/touch";
import { EyeBridge } from "./vision/ts/eye_bridge";

const touch = new TouchSenses(0);
const eyes = new EyeBridge();

const visionHost = process.env.VISION_HOST ?? "127.0.0.1";
console.log("--- Furbacca Nervous System: Modular Edition ---");
console.log(`Eyes: ${visionHost}:5005 | Touch: BCM 17 (head), 22 (belly), ${VIBE_BCM} (vibration)`);

function handleBellyTouch(): void {
  console.log("🐾 Belly touch: Cycling species");
  eyes.cycleEyeType();
  eyes.sendCommand("look", { x: 0, y: 0, pupil_mode: "wide" });
}

function onTouch(sensor: "head" | "belly" | "shiver", active: boolean): void {
  if (!active) return;
  if (sensor === "head") {
    console.log("🐾 Head touch");
    eyes.blink();
    eyes.playAnimation("nervous_look", { replace: true });
  } else if (sensor === "belly") {
    handleBellyTouch();
  } else if (sensor === "shiver") {
    console.log(`🫨 SHIVER: BCM ${VIBE_BCM} detected vibration (Logic 0)`);
    eyes.impulse();
  }
}

// Prefer event-driven (gpiomon) for minimal latency; fall back to 20ms polling
const stopEventWatch = touch.startEventWatch(onTouch);
if (stopEventWatch) {
  console.log("  Touch: event-driven (gpiomon)");
  process.on("SIGINT", () => {
    stopEventWatch();
    process.exit(0);
  });
} else {
  console.log("  Touch: polling every 20ms (install gpiomon for event-driven)");
  setInterval(() => touch.poll(onTouch), 20);
}
