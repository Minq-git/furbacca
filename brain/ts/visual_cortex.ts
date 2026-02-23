import * as dgram from "node:dgram";

import { msg, substitute } from "../../messages.js";
import type { EyeTrackingEvent } from "../../synapses/ts/vision_messages.js";
import type { EyeBridge } from "../../vision/ts/eye_bridge.js";

/** UDP port for local events (e.g. eye-track.sh notifies when tracking starts/stops). */
const NS_EVENTS_PORT = 5006;

/** Throttle "in view" / "left view" logs (camera can flicker at frame edge). */
const LOOKING_LOG_INTERVAL_MS = 4000;

export class VisualCortex {
	private socket: dgram.Socket | null = null;
	private lastLookingStartedLog = 0;
	private lastLookingStoppedLog = 0;

	// biome-ignore lint/complexity/noUselessConstructor: intentionally unused.
	constructor(_eyes: EyeBridge) {
		// Intentionally unused: cortex logic may drive eyes later (triggered vs casual look).
	}

	public startListening(): void {
		if (this.socket) return;
		const sock = dgram.createSocket("udp4");
		this.socket = sock;

		sock.bind(NS_EVENTS_PORT, "127.0.0.1", () => {
			sock.on("message", (buf: Buffer) => {
				try {
					const payload = JSON.parse(buf.toString()) as EyeTrackingEvent;
					if (payload.event === "eye_tracking_started") {
						console.log(msg.nervous_system.eye_tracking_started);
						return;
					}
					if (payload.event === "eye_tracking_stopped") {
						console.log(msg.nervous_system.eye_tracking_stopped);
						return;
					}
					if (payload.event === "looking_started") {
						const now = Date.now();
						if (now - this.lastLookingStartedLog >= LOOKING_LOG_INTERVAL_MS) {
							this.lastLookingStartedLog = now;
							console.log(msg.nervous_system.looking_started);
						}
						return;
					}
					if (payload.event === "looking_stopped") {
						const now = Date.now();
						if (now - this.lastLookingStoppedLog >= LOOKING_LOG_INTERVAL_MS) {
							this.lastLookingStoppedLog = now;
							console.log(msg.nervous_system.looking_stopped);
						}
						return;
					}
					if (payload.event === "looking_at") {
						const p = payload;
						if (
							p.label != null &&
							p.confidence != null &&
							p.x != null &&
							p.y != null
						) {
							console.log(
								substitute(msg.nervous_system.looking_at, {
									label: p.label,
									confidence: String(p.confidence),
									x: String(p.x),
									y: String(p.y),
								}),
							);
						}
					}
				} catch {
					/* ignore malformed */
				}
			});
		});
	}

	public async stopListening(): Promise<void> {
		const sock = this.socket;
		this.socket = null;
		if (!sock) return;
		await new Promise<void>((resolve) => {
			try {
				sock.close(() => resolve());
			} catch {
				resolve();
			}
		});
	}
}
