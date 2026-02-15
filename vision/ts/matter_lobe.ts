/**
 * Matter Lobe: The Bridge to the Smart Home Universe.
 *
 * Goal: Expose Furbacca as a composed device with two endpoints:
 *   - Endpoint 1 (The Head): ExtendedColorLight — Hue/Brightness sliders → Eyes/Species
 *   - Endpoint 2 (The Belly): GenericSwitch (Momentary) — Belly sensor as programmable button in Google Home
 *
 * Matter.js 0.12 exposes two APIs:
 *   - Legacy: CommissioningServer + MatterServer + device/Endpoint (addEndpoint is protected; extend CommissioningServer).
 *   - New: ServerNode with root endpoint and parts; Environment from @matter/nodejs.
 *
 * This module currently stubs Matter startup so the nervous system runs. To complete:
 *   - Use Legacy API (CommissioningServer, MatterServer, DeviceTypes.EXTENDED_COLOR_LIGHT / GENERIC_SWITCH)
 *     with a custom CommissioningServer subclass that adds the two device endpoints in its constructor, or
 *   - Use New API (ServerNode.create with RootEndpoint, then root.parts.add(ExtendedColorLightDevice), etc.)
 *     and provide Environment (storage/network from @matter/nodejs).
 */
import { EyeBridge } from "./eye_bridge";
import { TouchSenses } from "../../senses/touch";

export class MatterLobe {
  private eyes: EyeBridge;
  private touch: TouchSenses;

  constructor(eyes: EyeBridge, touch: TouchSenses) {
    this.eyes = eyes;
    this.touch = touch;
  }

  async start(): Promise<void> {
    console.log("  🧠 Matter Lobe: Initializing...");

    try {
      // Optional: load Matter and start when the full implementation is in place.
      // const matter = await import("@project-chip/matter.js");
      // const matterNode = await import("@project-chip/matter-node.js");
      console.log("  🧠 Matter Lobe: Stub (composed device API not yet wired).");
      console.log("  ↳ Endpoint 1: Extended Color Light.");
      console.log("  ↳ Endpoint 2: Generic Switch.");
    } catch (err) {
      console.error("  🧠 Matter Lobe: Failed to start.", err);
      throw err;
    }
  }
}
