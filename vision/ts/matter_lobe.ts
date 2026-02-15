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

export type TouchSensor = "head" | "belly" | "shiver";

export class MatterLobe {
  private eyes: EyeBridge;
  private touch: TouchSenses;
  private matterNode: unknown = undefined;
  /** Set after endpoints are ready; used to forward touch events from nervous_system (single GPIO owner). */
  private onTouchForMatter: ((sensor: TouchSensor, active: boolean) => void) | null = null;

  constructor(eyes: EyeBridge, touch: TouchSenses) {
    this.eyes = eyes;
    this.touch = touch;
  }

  /** Call when touch is event-driven (gpiomon). Do not use touch.poll() — it conflicts with gpiomon. */
  notifyTouch(sensor: TouchSensor, active: boolean): void {
    this.onTouchForMatter?.(sensor, active);
  }

  /** Release Matter node resources on shutdown. Call before process.exit for clean CTRL+C. */
  close(): void {
    this.onTouchForMatter = null;
    // Matter SDK may not expose node.close(); OS will reclaim port/process on exit.
  }

  async start(options?: {
    onStatus?: (msg: string) => void;
    /** If set, Matter SDK log lines are buffered here instead of printed; caller prints after start() to keep order. */
    matterLogBuffer?: string[];
  }): Promise<void> {
    const status = (msg: string) => {
      if (options?.onStatus) options.onStatus(msg);
      else console.log("  🧠 Matter Lobe: " + msg);
    };
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
      status("Initializing (single stack 0.12)...");
      const general = await import("@matter/general");
      const { Logger, LogLevel } = general;
      const pairingQrPattern = /Commissioning|passcode|discriminator|pairing|uncommissioned|qrcode|QR code|manual pairing|▄|▀|█|project-chip\.github\.io/i;
      const defaultDef = Logger.logger.find((l) => l.logIdentifier === "default");
      if (defaultDef) {
        const originalLog = defaultDef.log;
        const buffer = options?.matterLogBuffer;
        defaultDef.log = (level: number, formattedLog: string) => {
          const shouldEmit = level >= LogLevel.WARN || pairingQrPattern.test(formattedLog);
          if (!shouldEmit) return;
          if (buffer) buffer.push(formattedLog);
          else originalLog(level, formattedLog);
        };
      }
      await import("@project-chip/matter-node.js");
      const { ServerNode } = await import("@matter/node");
      const {
        ExtendedColorLightDeviceDefinition,
        GenericSwitchDeviceDefinition,
        GenericSwitchRequirements,
      } = await import("@matter/node/devices");

      status(`Checking UDP port ${MATTER_UDP_PORT} ...`);
      if (!(await isUdpPortFree(MATTER_UDP_PORT))) {
        console.warn(`  🧠 Matter Lobe: UDP port ${MATTER_UDP_PORT} is in use. Free it or stop the other process.`);
        throw new Error(`Matter requires UDP port ${MATTER_UDP_PORT}; it is already bound.`);
      }
      status("Port free. Creating ServerNode (this may take a minute)...");
      this.matterNode = await ServerNode.create();
      const node = this.matterNode as Awaited<ReturnType<typeof ServerNode.create>>;
      status("Node created. Adding endpoints...");

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

      // Identify: when user taps "Identify" in a smart home app, blink so they can see which device it is
      const identify = (ev as Record<string, { startIdentifying?: { on: (cb: () => void) => void }; identifyTime$Changed?: { on: (cb: (v: unknown) => void) => void } }>).identify;
      if (identify?.startIdentifying?.on) {
        identify.startIdentifying.on(() => {
          console.log("  🧠 Matter: Identify command received!");
          this.eyes.blink();
        });
      } else if (identify?.identifyTime$Changed?.on) {
        identify.identifyTime$Changed.on((v) => {
          if ((v as number) > 0) {
            console.log("  🧠 Matter: Identify command received!");
            this.eyes.blink();
          }
        });
      }

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

      // Stub Identify on switch endpoints (no eyes to blink; just log so the cluster is handled)
      const attachIdentifyStub = (
        endpoint: Awaited<ReturnType<InstanceType<typeof ServerNode>["add"]>>,
        label: string
      ) => {
        const events = endpoint.events as Record<string, { startIdentifying?: { on: (cb: () => void) => void }; identifyTime$Changed?: { on: (cb: (v: unknown) => void) => void } }>;
        const id = events?.identify;
        if (id?.startIdentifying?.on) id.startIdentifying.on(() => console.log(`  🧠 Matter: Identify on ${label}`));
        else if (id?.identifyTime$Changed?.on) id.identifyTime$Changed.on((v) => { if ((v as number) > 0) console.log(`  🧠 Matter: Identify on ${label}`); });
      };

      const bellyEndpoint = await node.add(SwitchDevice as unknown as Parameters<typeof node.add>[0], {
        id: "belly",
      } as Parameters<typeof node.add>[1]);
      await setMomentaryFeatureMap(bellyEndpoint);
      attachIdentifyStub(bellyEndpoint, "belly");
      const bellyEv = bellyEndpoint.events as SwitchEvents;

      const headEndpoint = await node.add(SwitchDevice as unknown as Parameters<typeof node.add>[0], {
        id: "head",
      } as Parameters<typeof node.add>[1]);
      await setMomentaryFeatureMap(headEndpoint);
      attachIdentifyStub(headEndpoint, "head");
      const headEv = headEndpoint.events as SwitchEvents;

      const shakeEndpoint = await node.add(SwitchDevice as unknown as Parameters<typeof node.add>[0], {
        id: "shake",
      } as Parameters<typeof node.add>[1]);
      await setMomentaryFeatureMap(shakeEndpoint);
      attachIdentifyStub(shakeEndpoint, "shake");
      const shakeEv = shakeEndpoint.events as SwitchEvents;
      const SHAKE_COOLDOWN_MS = 1500;
      let lastShakeEmitAt = 0;

      // Single source of touch: nervous_system (gpiomon). Do not call touch.poll() — it uses gpioget and conflicts with gpiomon.
      this.onTouchForMatter = (sensor: TouchSensor, active: boolean) => {
        if (sensor === "belly" && active) emitMomentaryPress(bellyEv, "Belly Press");
        if (sensor === "head" && active) emitMomentaryPress(headEv, "Head Touch");
        if (sensor === "shiver" && active) {
          const now = Date.now();
          if (now - lastShakeEmitAt >= SHAKE_COOLDOWN_MS) {
            lastShakeEmitAt = now;
            emitMomentaryPress(shakeEv, "Shake");
          }
        }
      };

      status("Endpoints ready. Starting node...");
      await node.start();
      status("Online. Generating pairing code and QR below...");
    };

    await Promise.race([doStart(), timeoutPromise]);
  }
}
