import { TouchSenses } from "./senses/touch";
import { playGiggle } from "./sounds/audio";
import { EyeBridge } from "./vision/eye_bridge";

const touch = new TouchSenses(0); // chip 0 for Pi Zero 2 W
const eyes = new EyeBridge();

console.log("--- Furbacca Nervous System: Modular Edition ---");

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
