/**
 * Touch sensors (TTP223B) via gpioget. SW-420 vibration on BCM 23.
 * Head: BCM 17. Belly: BCM 22. Vibration DO: BCM 23 (Logic 0 = detected).
 */
import { execSync } from "child_process";

const VIBE_BCM = 23;

export class TouchSenses {
  private chipNum: number;
  private lastHead: number = 0;
  private lastBelly: number = 0;
  private lastVibe: number = 1;

  constructor(chip: number) {
    this.chipNum = chip;
  }

  private readPins(): [number, number, number] {
    try {
      // GPIO 17 (Head), 22 (Belly), 23 (Vibration SW-420 DO)
      const out = execSync(`gpioget -c ${this.chipNum} --numeric 17 22 23`, {
        encoding: "utf-8",
      });
      const parts = out.trim().split(/\s+/);
      return [parseInt(parts[0], 10), parseInt(parts[1], 10), parseInt(parts[2], 10)];
    } catch {
      return [0, 0, 1]; // Default vibe to 1 (NC state)
    }
  }

  public poll(callback: (type: "head" | "belly" | "shiver", state: boolean) => void): void {
    const [head, belly, vibe] = this.readPins();
    if (head !== this.lastHead) {
      this.lastHead = head;
      callback("head", !!head);
    }
    if (belly !== this.lastBelly) {
      this.lastBelly = belly;
      callback("belly", !!belly);
    }
    if (vibe !== this.lastVibe) {
      this.lastVibe = vibe;
      if (vibe === 0) {
        callback("shiver", true);
      }
    }
  }
}

export { VIBE_BCM };
