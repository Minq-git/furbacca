import { execSync } from "child_process";

export class TouchSenses {
  private chipNum: number;
  private lastHead: number = 0;
  private lastBelly: number = 0;

  constructor(chip: number) {
    this.chipNum = chip;
  }

  private readPins(): [number, number] {
    try {
      const out = execSync(`gpioget -c ${this.chipNum} --numeric 17 22`, { encoding: "utf-8" });
      const parts = out.trim().split(/\s+/);
      return [parseInt(parts[0]), parseInt(parts[1])];
    } catch {
      return [0, 0];
    }
  }

  public poll(callback: (type: 'head' | 'belly', state: boolean) => void) {
    const [head, belly] = this.readPins();
    if (head !== this.lastHead) {
      this.lastHead = head;
      callback('head', !!head);
    }
    if (belly !== this.lastBelly) {
      this.lastBelly = belly;
      callback('belly', !!belly);
    }
  }
}