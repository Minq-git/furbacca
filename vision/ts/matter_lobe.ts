/**
 * Matter Lobe: The Bridge to the Smart Home Universe.
 *
 * Exposes Furbacca as a composed device with four endpoints:
 *   - Endpoint 1 (Light): Eyes — OnOff/Level/Hue → eyes (impulse, animations, species)
 *   - Endpoint 2 (Switch): Belly Touch Sensor — programmable button in Google Home
 *   - Endpoint 3 (Switch): Head Touch Sensor — programmable button in Google Home
 *   - Endpoint 4 (Switch): Vibration/Shake (SW-420), debounced to reduce noise
 *
 * Uses Matter.js 0.12+ behavior/endpoint API. Requires Node.js environment (import @project-chip/matter-node.js).
 * Next steps: ensure UDP port 5540 is free; pairing/certificate storage uses .matter/ (in .gitignore).
 */
import "@project-chip/matter-node.js"; // Side effect: sets Environment.default for Node.js
import { ServerNode } from "@matter/node";
import {
  ExtendedColorLightDeviceDefinition,
  GenericSwitchDeviceDefinition,
  GenericSwitchRequirements,
} from "@matter/node/devices";
import { EyeBridge } from "./eye_bridge.js";
import { TouchSenses } from "../../senses/touch.js";

export class MatterLobe {
  private eyes: EyeBridge;
  private touch: TouchSenses;
  private matterNode: InstanceType<typeof ServerNode> | undefined;

  constructor(eyes: EyeBridge, touch: TouchSenses) {
    this.eyes = eyes;
    this.touch = touch;
  }

  async start(): Promise<void> {
    console.log("  🧠 Matter Lobe: Initializing (v0.12 API)...");

    // Create the node (uses Environment.default from matter-node.js)
    this.matterNode = await ServerNode.create();

    // Endpoint 1: Eyes (Extended Color Light)
    const eyeEndpoint = await this.matterNode.add(ExtendedColorLightDeviceDefinition);

    // --- On/Off → Sleep/Wake (behavior id: onOff) ---
    const ev = eyeEndpoint.events as Record<string, Record<string, { on?: (cb: (v: unknown) => void) => void }>>;
    if (ev.onOff?.onOff$Changed?.on) {
      ev.onOff.onOff$Changed.on((v) => {
        const isOn = v as boolean;
        console.log("  🧠 Matter: OnOff changed to", isOn);
        if (isOn) {
          this.eyes.impulse();
          this.eyes.setEyeShape("round");
        } else {
          this.eyes.blink();
        }
      });
    }

    // --- Level (brightness) → nervous look when low ---
    if (ev.levelControl?.currentLevel$Changed?.on) {
      ev.levelControl.currentLevel$Changed.on((v) => {
        const level = v as number | null;
        if (level == null) return;
        console.log("  🧠 Matter: Brightness/Level set to", level);
        if (level < 50) this.eyes.playAnimation("nervous_look");
      });
    }

    // --- Hue → species ---
    if (ev.colorControl?.currentHue$Changed?.on) {
      ev.colorControl.currentHue$Changed.on((v) => {
        const hue = v as number | null;
        if (hue == null) return;
        console.log("  🧠 Matter: Hue set to", hue);
        if (hue < 20 || hue > 230) {
          this.eyes.sendCommand("set_eye_type", { type: "demon" });
        } else if (hue > 60 && hue < 100) {
          this.eyes.sendCommand("set_eye_type", { type: "dragon" });
        } else {
          this.eyes.sendCommand("set_eye_type", { type: "human" });
        }
      });
    }

    const SwitchDevice = GenericSwitchDeviceDefinition.with(GenericSwitchRequirements.SwitchServer);
    const setMomentaryFeatureMap = async (endpoint: Awaited<ReturnType<InstanceType<typeof ServerNode>["add"]>>) => {
      try {
        await endpoint.set({
          switch: {
            featureMap: {
              momentarySwitch: true,
              latchingSwitch: false,
              actionSwitch: false,
            },
          },
        } as any);
      } catch (e) {
        console.warn("  🧠 Matter: Could not set switch featureMap:", e);
      }
    };

    type SwitchEvents = Record<string, { initialPress?: { emit: (v: { newPosition: number }) => void }; shortRelease?: { emit: (v: { previousPosition: number }) => void } }>;
    const emitMomentaryPress = (ev: SwitchEvents, label: string) => {
      if (!ev.switch?.initialPress?.emit) return;
      console.log("  🧠 Matter: Broadcasting", label, "event");
      ev.switch.initialPress.emit({ newPosition: 1 });
      setTimeout(() => {
        ev.switch?.shortRelease?.emit?.({ previousPosition: 1 });
      }, 100);
    };

    // Endpoint 2: Belly (Generic Switch, momentary)
    const bellyEndpoint = await this.matterNode.add(SwitchDevice);
    await setMomentaryFeatureMap(bellyEndpoint);
    const bellyEv = bellyEndpoint.events as SwitchEvents;

    // Endpoint 3: Head touch (Generic Switch, momentary)
    const headEndpoint = await this.matterNode.add(SwitchDevice);
    await setMomentaryFeatureMap(headEndpoint);
    const headEv = headEndpoint.events as SwitchEvents;

    // Endpoint 4: Vibration/Shake (Generic Switch, momentary). Debounce to avoid SW-420 noise.
    const shakeEndpoint = await this.matterNode.add(SwitchDevice);
    await setMomentaryFeatureMap(shakeEndpoint);
    const shakeEv = shakeEndpoint.events as SwitchEvents;
    const SHAKE_COOLDOWN_MS = 1500;
    let lastShakeEmitAt = 0;

    this.touch.poll((sensor, active) => {
      if (sensor === "belly" && active) {
        emitMomentaryPress(bellyEv, "Belly Press");
      }
      if (sensor === "head" && active) {
        emitMomentaryPress(headEv, "Head Touch");
      }
      if (sensor === "shiver" && active) {
        const now = Date.now();
        if (now - lastShakeEmitAt >= SHAKE_COOLDOWN_MS) {
          lastShakeEmitAt = now;
          emitMomentaryPress(shakeEv, "Shake");
        }
      }
    });

    await this.matterNode.start();
    console.log("  🧠 Matter Lobe: Online. Check logs for pairing QR code.");
  }
}
