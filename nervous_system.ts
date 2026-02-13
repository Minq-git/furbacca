import { TouchSenses } from "./senses/touch";
import { playGiggle } from "./sounds/ts/audio";
import { EyeBridge } from "./vision/ts/eye_bridge";

const touch = new TouchSenses(0); // chip 0 for Pi Zero 2 W
const eyes = new EyeBridge();

const visionHost = process.env.VISION_HOST ?? "127.0.0.1";
console.log("--- Furbacca Nervous System: Modular Edition ---");
console.log(`Eyes: ${visionHost}:5005 | Touch: BCM 17 (head), 22 (belly)`);

/**
 * Placeholder for belly touch (BCM 22). Expand with fan, eyes, or other behaviors.
 */
function handleBellyTouch(): void {
  console.log("🐾 Belly touch");
  eyes.sendCommand("cycle_eye_type");
}

setInterval(() => {
  touch.poll((sensor, active) => {
    if (active) {
      if (sensor === "head") {
        console.log("🐾 Head touch");
        console.log("🔊 Sound: giggle");
        playGiggle();
        eyes.sendCommand("blink");
        eyes.playAnimation("nervous_look");
      } else if (sensor === "belly") {
        handleBellyTouch();
      }
    }
  });
}, 20);
