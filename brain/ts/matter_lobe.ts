/**
 * Matter Lobe: Furbacca as a Matter device (single stack @project-chip/matter-node.js 0.12).
 *
 * Endpoints:
 *   - 1: Extended Color Light (eyes) — OnOff/Level/Hue → eyes (impulse, animations, species).
 *   - 2: Generic Switch (belly touch).
 *   - 3: Generic Switch (head touch).
 *   - 4: Generic Switch (vibration/shake).
 *
 * Lazy-loaded when start() runs. UDP 5540.
 * Storage (fabric, CASE, pairing) is in repo .matter/ so it persists across restarts.
 * Do not set MATTER_STORAGE_CLEAR=1 in production or devices will go offline after reboot.
 */
import * as dgram from "dgram";
import * as fs from "fs/promises";
import * as path from "path";
import { msg, substitute } from "../../messages.js";
import { EyeBridge } from "../../vision/ts/eye_bridge.js";
import { TouchSenses } from "../../senses/touch.js";

const MATTER_UDP_PORT = 5540;
const MATTER_STARTUP_TIMEOUT_MS = 90_000;

/** Keys in root.generalDiagnostics that can fail to parse after SDK/storage schema changes; remove before create so SDK re-initializes them. */
const CORRUPT_GENERAL_DIAGNOSTICS_KEYS = ["__features__", "totalOperationalHoursCounter"];

/** Matter storage in repo so factory reset (rm -rf .matter) clears commissioning. Anchored to __dirname so path is stable under systemd (WorkingDirectory may differ). */
const REPO_ROOT = path.resolve(__dirname, "../../.."); // dist/brain/ts → repo root
function getMatterDir(): string {
  return path.join(REPO_ROOT, ".matter");
}

async function tidyMatterStorage(): Promise<void> {
  const matterDir = getMatterDir();
  try {
    const entries = await fs.readdir(matterDir, { withFileTypes: true });
    for (const ent of entries) {
      if (!ent.isDirectory()) continue;
      const subPath = path.join(matterDir, ent.name);
      const files = await fs.readdir(subPath);
      for (const file of files) {
        try {
          const decoded = decodeURIComponent(file);
          const isCorrupt =
            decoded.includes("generalDiagnostics") &&
            CORRUPT_GENERAL_DIAGNOSTICS_KEYS.some((k) => decoded.endsWith(`.${k}`));
          if (isCorrupt) await fs.unlink(path.join(subPath, file));
        } catch {
          /* ignore unlink/decode errors */
        }
      }
    }
  } catch {
    /* .matter missing or unreadable is fine */
  }
}

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
  async close(): Promise<void> {
    this.onTouchForMatter = null;
    if (this.matterNode && typeof (this.matterNode as { close?: () => Promise<void> }).close === "function") {
      await (this.matterNode as { close: () => Promise<void> }).close(); // Flushes storage and announces shutdown via mDNS
    }
  }

  async start(options?: {
    onStatus?: (msg: string) => void;
    /** If set, Matter SDK log lines are buffered here instead of printed; caller prints after start() to keep order. */
    matterLogBuffer?: string[];
    /** If true, use short "Online." instead of "Online. Generating pairing code and QR below...". */
    pairingAlreadyShown?: boolean;
  }): Promise<void> {
    const status = (s: string) => {
      if (options?.onStatus) options.onStatus(s);
      else console.log(msg.nervous_system.matter_lobe_prefix + s);
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
      status(msg.matter_lobe.status.initializing);
      // Pin storage to repo .matter/ before any Matter env init (so factory reset clears commissioning)
      const matterNodejsConfig = await import("@matter/nodejs/config");
      matterNodejsConfig.config.defaultStoragePath = getMatterDir();
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
      const { DeviceTypeId, VendorId } = await import("@matter/types");
      const devices = await import("@matter/node/devices");
      const { GenericSwitchDeviceDefinition, GenericSwitchRequirements } = devices;
      const { ExtendedColorLightDeviceDefinition, ExtendedColorLightRequirements } = devices;
      const { createFurbaccaExtendedColorLight, EyeBridgeForIdentify } = await import(
        "./furbacca_identify_server.js"
      );
      const FurbaccaExtendedColorLightDeviceDefinition = createFurbaccaExtendedColorLight(
        ExtendedColorLightDeviceDefinition as { with: (...behaviors: unknown[]) => unknown },
        ExtendedColorLightRequirements as { IdentifyServer: new (...args: unknown[]) => { endpoint: unknown } }
      );

      // Lock storage path and disable clear on default environment (Matter 0.8+ style; reinforces config.defaultStoragePath).
      const env = general.Environment.default;
      const storagePath = getMatterDir();
      env.vars.set("storage.path", storagePath);
      env.vars.set("storage.clear", false);

      status(substitute(msg.matter_lobe.status.checking_port, { port: String(MATTER_UDP_PORT) }));
      if (!(await isUdpPortFree(MATTER_UDP_PORT))) {
        console.warn(substitute(msg.matter_lobe.udp_port_in_use, { port: String(MATTER_UDP_PORT) }));
        throw new Error(`Matter requires UDP port ${MATTER_UDP_PORT}; it is already bound.`);
      }
      status(msg.matter_lobe.status.port_free);
      await tidyMatterStorage();
      this.matterNode = await ServerNode.create(ServerNode.RootEndpoint, {
        id: "furbacca-brain-node",
        network: {
          port: MATTER_UDP_PORT,
          ipv4: true, // IPv4-only reduces CPU on Pi Zero 2 W; set MATTER_MDNS_NETWORKINTERFACE=wlan0 if needed
        },
        // Fixed commissioning credentials. Storage path must be set before SDK init (see above) so the SDK
        // uses this config and not random/stale values from another directory; a hub–device mismatch
        // (e.g. hub using cached discriminator 2372 while we advertise 3840) causes a 30s commissioning timeout.
        commissioning: {
          passcode: 20202021,
          discriminator: 3840,
        },
        productDescription: {
          name: "Furbacca",
          deviceType: DeviceTypeId(0x010d), // Extended Color Light
        },
        basicInformation: {
          vendorName: "Minqz",
          vendorId: VendorId(0xfff1, false), // 0xFFF1 = Test Vendor
          productName: "Furbacca Smart Home Assistant",
          productId: 0x8000,
          nodeLabel: "Furbacca",
          serialNumber: "FURB-001",
          uniqueId: "Furbacca-001",
          hardwareVersion: 1,
          hardwareVersionString: "v1.0",
          softwareVersion: 1,
          softwareVersionString: "v1.0",
          capabilityMinima: { caseSessionsPerFabric: 3, subscriptionsPerFabric: 3 },
        },
      });
      const node = this.matterNode as Awaited<ReturnType<typeof ServerNode.create>>;
      status(msg.matter_lobe.status.node_created);

      // Endpoint 1: Eyes (Extended Color Light with custom Identify triggerEffect → Furbacca animations)
      node.env.set(EyeBridgeForIdentify, this.eyes);
      const eyeEndpoint = await node.add(
        FurbaccaExtendedColorLightDeviceDefinition as unknown as Parameters<typeof node.add>[0],
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
          console.log(substitute(msg.matter_lobe.onoff_changed, { value: String(isOn) }));
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
          console.log(substitute(msg.matter_lobe.brightness_set, { level: String(level) }));
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
          console.log(substitute(msg.matter_lobe.xy_x_set, { x: String(x) }));
          applyXyToSpecies();
        });
      if (ev.colorControl?.currentY$Changed?.on)
        ev.colorControl.currentY$Changed.on((v) => {
          const y = v as number | null;
          if (y == null) return;
          lastY = y;
          console.log(substitute(msg.matter_lobe.xy_y_set, { y: String(y) }));
          applyXyToSpecies();
        });
      if (ev.colorControl?.currentHue$Changed?.on)
        ev.colorControl.currentHue$Changed.on((v) => {
          const hue = v as number | null;
          if (hue == null) return;
          console.log(substitute(msg.matter_lobe.hue_set, { hue: String(hue) }));
          applyHueToSpecies(hue, this.eyes);
        });
      // Color temperature (e.g. "Warm White" / "Cool White"): high mireds = warm → human, low = cool → demon
      const evColor = ev.colorControl as Record<string, { on?: (cb: (v: unknown) => void) => void } | undefined> | undefined;
      if (evColor?.colorTemperatureMireds$Changed?.on) {
        evColor.colorTemperatureMireds$Changed.on((v) => {
          const mireds = v as number | null;
          if (mireds == null) return;
          if (mireds >= 350) this.eyes.sendCommand("set_eye_type", { type: "human" });
          else if (mireds <= 200) this.eyes.sendCommand("set_eye_type", { type: "demon" });
        });
      }

      // Identify: when user taps "Identify" in a smart home app, blink so they can see which device it is
      const identify = (ev as Record<string, { startIdentifying?: { on: (cb: () => void) => void }; identifyTime$Changed?: { on: (cb: (v: unknown) => void) => void } }>).identify;
      if (identify?.startIdentifying?.on) {
        identify.startIdentifying.on(() => {
          console.log(msg.matter_lobe.identify_received);
          this.eyes.blink();
        });
      } else if (identify?.identifyTime$Changed?.on) {
        identify.identifyTime$Changed.on((v) => {
          if ((v as number) > 0) {
            console.log(msg.matter_lobe.identify_received);
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
          console.warn(substitute(msg.matter_lobe.switch_featuremap_warn, { error: String(e) }));
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
        console.log(substitute(msg.matter_lobe.broadcasting, { label }));
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
        if (id?.startIdentifying?.on) id.startIdentifying.on(() => console.log(substitute(msg.matter_lobe.identify_on, { label })));
        else if (id?.identifyTime$Changed?.on) id.identifyTime$Changed.on((v) => { if ((v as number) > 0) console.log(substitute(msg.matter_lobe.identify_on, { label })); });
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

      status(msg.matter_lobe.status.endpoints_ready);
      await node.start();
      status(
        options?.pairingAlreadyShown
          ? (msg.matter_lobe.status as { online_short?: string }).online_short ?? "Online."
          : msg.matter_lobe.status.online
      );

      // Only show pairing/QR when uncommissioned; if already paired, remove those lines from the log buffer and delete cached pairing display
      const buffer = options?.matterLogBuffer;
      if (buffer?.length && node.lifecycle.isCommissioned) {
        const pairingQrPattern = /Commissioning|passcode|discriminator|pairing|uncommissioned|qrcode|QR code|manual pairing|▄|▀|█|project-chip\.github\.io/i;
        for (let i = buffer.length - 1; i >= 0; i--) {
          if (pairingQrPattern.test(buffer[i]!)) buffer.splice(i, 1);
        }
        try {
          await fs.unlink(path.join(getMatterDir(), "pairing_display.txt"));
        } catch {
          /* ignore */
        }
      }
    };

    await Promise.race([doStart(), timeoutPromise]);
  }
}
