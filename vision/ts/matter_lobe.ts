/**
 * Matter Lobe: Furbacca as a Matter device (single stack @project-chip/matter-node.js 0.12).
 *
 * Endpoints:
 *   - 1: Extended Color Light (eyes) — OnOff/Level/Hue → eyes (impulse, animations, species).
 *   - 2: Generic Switch (belly touch).
 *   - 3: Generic Switch (head touch).
 *   - 4: Generic Switch (vibration/shake).
 *
 * Lazy-loaded when start() runs. UDP 5540; pairing data in .matter/
 */
import * as dgram from "dgram";
import { EyeBridge } from "./eye_bridge.js";
import { TouchSenses } from "../../senses/touch.js";

const MATTER_UDP_PORT = 5540;
const MATTER_STARTUP_TIMEOUT_MS = 90_000;

function isUdpPortFree(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = dgram.createSocket("udp4");
    socket.once("error", () => {
      socket.close();
      resolve(false);
    });
    socket.once("listening", () => {
      socket.close(() => resolve(true));
    });
    socket.bind(port);
  });
}

function applyHueToSpecies(hue: number, eyes: EyeBridge): void {
  if (hue < 20 || hue > 230) {
    eyes.sendCommand("set_eye_type", { type: "demon" });
  } else if (hue > 60 && hue < 100) {
    eyes.sendCommand("set_eye_type", { type: "dragon" });
  } else {
    eyes.sendCommand("set_eye_type", { type: "human" });
  }
}

export class MatterLobe {
  private eyes: EyeBridge;
  private touch: TouchSenses;
  private matterNode: unknown = undefined;

  constructor(eyes: EyeBridge, touch: TouchSenses) {
    this.eyes = eyes;
    this.touch = touch;
  }

  async start(): Promise<void> {
    const timeoutPromise = new Promise<never>((_, reject) => {
      setTimeout(
        () =>
          reject(
            new Error(
              `Matter Lobe startup timed out after ${MATTER_STARTUP_TIMEOUT_MS / 1000}s. Check .matter/ and port ${MATTER_UDP_PORT}.`
            )
          ),
        MATTER_STARTUP_TIMEOUT_MS
      );
    });

    const doStart = async (): Promise<void> => {
      console.log("  🧠 Matter Lobe: Initializing (single stack 0.12)...");
      await import("@project-chip/matter-node.js");
      const { ServerNode } = await import("@matter/node");
      const {
        ExtendedColorLightDeviceDefinition,
        GenericSwitchDeviceDefinition,
        GenericSwitchRequirements,
      } = await import("@matter/node/devices");

      console.log("  🧠 Matter Lobe: Checking UDP port", MATTER_UDP_PORT, "...");
      if (!(await isUdpPortFree(MATTER_UDP_PORT))) {
        console.warn(`  🧠 Matter Lobe: UDP port ${MATTER_UDP_PORT} is in use. Free it or stop the other process.`);
        throw new Error(`Matter requires UDP port ${MATTER_UDP_PORT}; it is already bound.`);
      }
      console.log("  🧠 Matter Lobe: Port free. Creating ServerNode (this may take a minute)...");
      this.matterNode = await ServerNode.create();
      const node = this.matterNode as Awaited<ReturnType<typeof ServerNode.create>>;
      console.log("  🧠 Matter Lobe: Node created. Adding endpoints...");

      // Endpoint 1: Eyes (Extended Color Light)
      // Extended Color Light mandates CT; provide all required attributes. id: "eyes" silences fallback ID warning.
      const eyeEndpoint = await node.add(
        ExtendedColorLightDeviceDefinition as unknown as Parameters<typeof node.add>[0],
        {
          id: "eyes",
          colorControl: {
            colorMode: 1, // CurrentXAndCurrentY (device has XY + CT, not HS)
            colorTemperatureMireds: 250, // ~4000K
            colorTempPhysicalMinMireds: 147, // ~6800K (cool)
            colorTempPhysicalMaxMireds: 500, // ~2000K (warm)
            coupleColorTempToLevelMinMireds: 250, // in [physicalMin, colorTemperatureMireds] per spec
            startUpColorTemperatureMireds: 250, // concrete value required by validator at startup
          },
        } as Parameters<typeof node.add>[1]
      );

      const ev = eyeEndpoint.events as unknown as Record<
        string,
        Record<string, { on?: (cb: (v: unknown) => void) => void }>
      >;
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
      if (ev.levelControl?.currentLevel$Changed?.on) {
        ev.levelControl.currentLevel$Changed.on((v) => {
          const level = v as number | null;
          if (level == null) return;
          console.log("  🧠 Matter: Brightness/Level set to", level);
          if (level < 50) this.eyes.playAnimation("nervous_look");
        });
      }
      // Device has XY (and CT), not HS — controllers will send XY. Map XY to species.
      let lastX: number | null = null;
      let lastY: number | null = null;
      const applyXyToSpecies = () => {
        if (lastX == null || lastY == null) return;
        // CIE xy (0..65279) → rough hue 0..254 for species: use angle in xy plane
        const x = lastX / 65536;
        const y = lastY / 65536;
        const angle = Math.atan2(y - 0.4, x - 0.3);
        const hue = Math.round(((angle / (2 * Math.PI) + 0.5) % 1) * 254);
        applyHueToSpecies(hue, this.eyes);
      };
      if (ev.colorControl?.currentX$Changed?.on)
        ev.colorControl.currentX$Changed.on((v) => {
          const x = v as number | null;
          if (x == null) return;
          lastX = x;
          console.log("  🧠 Matter: XY x set to", x);
          applyXyToSpecies();
        });
      if (ev.colorControl?.currentY$Changed?.on)
        ev.colorControl.currentY$Changed.on((v) => {
          const y = v as number | null;
          if (y == null) return;
          lastY = y;
          console.log("  🧠 Matter: XY y set to", y);
          applyXyToSpecies();
        });
      if (ev.colorControl?.currentHue$Changed?.on)
        ev.colorControl.currentHue$Changed.on((v) => {
          const hue = v as number | null;
          if (hue == null) return;
          console.log("  🧠 Matter: Hue set to", hue);
          applyHueToSpecies(hue, this.eyes);
        });

      const SwitchDevice = GenericSwitchDeviceDefinition.with(GenericSwitchRequirements.SwitchServer);
      const setMomentaryFeatureMap = async (
        endpoint: Awaited<ReturnType<InstanceType<typeof ServerNode>["add"]>>
      ) => {
        try {
          // Only set bits we enable; latchingSwitch/actionSwitch are not valid bitmap keys here
          await endpoint.set({
            switch: {
              featureMap: {
                momentarySwitch: true,
              },
            },
          } as never);
        } catch (e) {
          console.warn("  🧠 Matter: Could not set switch featureMap:", e);
        }
      };

      type SwitchEvents = Record<
        string,
        {
          initialPress?: { emit: (v: { newPosition: number }) => void };
          shortRelease?: { emit: (v: { previousPosition: number }) => void };
        }
      >;
      const emitMomentaryPress = (ev: SwitchEvents, label: string) => {
        if (!ev.switch?.initialPress?.emit) return;
        console.log("  🧠 Matter: Broadcasting", label, "event");
        ev.switch.initialPress.emit({ newPosition: 1 });
        setTimeout(() => {
          ev.switch?.shortRelease?.emit?.({ previousPosition: 1 });
        }, 100);
      };

      const bellyEndpoint = await node.add(SwitchDevice as unknown as Parameters<typeof node.add>[0], {
        id: "belly",
      } as Parameters<typeof node.add>[1]);
      await setMomentaryFeatureMap(bellyEndpoint);
      const bellyEv = bellyEndpoint.events as SwitchEvents;

      const headEndpoint = await node.add(SwitchDevice as unknown as Parameters<typeof node.add>[0], {
        id: "head",
      } as Parameters<typeof node.add>[1]);
      await setMomentaryFeatureMap(headEndpoint);
      const headEv = headEndpoint.events as SwitchEvents;

      const shakeEndpoint = await node.add(SwitchDevice as unknown as Parameters<typeof node.add>[0], {
        id: "shake",
      } as Parameters<typeof node.add>[1]);
      await setMomentaryFeatureMap(shakeEndpoint);
      const shakeEv = shakeEndpoint.events as SwitchEvents;
      const SHAKE_COOLDOWN_MS = 1500;
      let lastShakeEmitAt = 0;

      this.touch.poll((sensor, active) => {
        if (sensor === "belly" && active) emitMomentaryPress(bellyEv, "Belly Press");
        if (sensor === "head" && active) emitMomentaryPress(headEv, "Head Touch");
        if (sensor === "shiver" && active) {
          const now = Date.now();
          if (now - lastShakeEmitAt >= SHAKE_COOLDOWN_MS) {
            lastShakeEmitAt = now;
            emitMomentaryPress(shakeEv, "Shake");
          }
        }
      });

      console.log("  🧠 Matter Lobe: Endpoints ready. Starting node...");
      await node.start();
      console.log("  🧠 Matter Lobe: Online. Check logs for pairing QR code.");
    };

    await Promise.race([doStart(), timeoutPromise]);
  }
}
