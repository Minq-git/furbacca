import * as dgram from "node:dgram";
import { msg, substitute } from "../../messages.js";

/** Pre-allocated buffers for high-frequency commands to avoid JSON.stringify + Buffer alloc on every call (reduces GC on Pi). */
const PAYLOAD_IMPULSE = Buffer.from(JSON.stringify({ action: "impulse" }));
const PAYLOAD_BLINK = Buffer.from(JSON.stringify({ action: "blink" }));
const PAYLOAD_CYCLE_EYE_TYPE = Buffer.from(
	JSON.stringify({ action: "cycle_eye_type" }),
);
const PAYLOAD_EYES_OPEN = Buffer.from(JSON.stringify({ action: "eyes_open" }));
const PAYLOAD_EYES_CLOSE = Buffer.from(
	JSON.stringify({ action: "eyes_close" }),
);

/** Cache for animation messages by name (replace flag varies). */
const animationCache = new Map<string, Buffer>();

function getAnimationPayload(name: string, replace: boolean): Buffer {
	const key = `${name}:${replace}`;
	let buf = animationCache.get(key);
	if (!buf) {
		buf = Buffer.from(JSON.stringify({ action: "animation", name, replace }));
		animationCache.set(key, buf);
	}
	return buf;
}

export class EyeBridge {
	private client = dgram.createSocket("udp4");
	private readonly HOST = process.env.VISION_HOST ?? "127.0.0.1";
	private readonly PORT = parseInt(process.env.VISION_PORT ?? "5005", 10);

	/** Send a raw payload (uses pre-allocated buffer when possible). */
	private send(payload: Buffer): void {
		this.client.send(payload, this.PORT, this.HOST, (err) => {
			if (err)
				console.error(
					substitute(msg.eye_bridge.error, { message: err.message }),
				);
		});
	}

	/** Generic command; for high-frequency actions use the specific methods to benefit from cached buffers. */
	public sendCommand(action: string, params: object = {}): void {
		const payload = Buffer.from(JSON.stringify({ action, ...params }));
		this.send(payload);
	}

	/** Play a named animation. Use replace: true to restart even if an animation is running (e.g. double head-tap). */
	public playAnimation(name: string, options?: { replace?: boolean }): void {
		const replace = options?.replace ?? false;
		this.send(getAnimationPayload(name, replace));
	}

	public setEyeShape(shape: string): void {
		console.log(substitute(msg.eyes.eye_shape, { shape }));
		this.sendCommand("set_eye_shape", { shape });
	}

	public cycleEyeShape(): void {
		console.log(substitute(msg.eyes.eye_shape, { shape: "(cycle)" }));
		this.sendCommand("cycle_eye_shape");
	}

	/** Impulse (shiver): uses pre-allocated buffer for rapid-fire. */
	public impulse(): void {
		this.send(PAYLOAD_IMPULSE);
	}

	/** Blink: uses pre-allocated buffer. */
	public blink(): void {
		this.send(PAYLOAD_BLINK);
	}

	/** Open lids (after startup: call when nervous system is ready). */
	public openEyes(): void {
		this.send(PAYLOAD_EYES_OPEN);
	}

	/** Close lids (e.g. before shutdown). */
	public closeEyes(): void {
		this.send(PAYLOAD_EYES_CLOSE);
	}

	/** Animated close for sleep (slow close, then hold closed). */
	public sleepClose(durationS?: number): void {
		this.sendCommand("sleep_close", { duration_s: durationS ?? 1 });
	}

	/** Warmup: send startup step 0..(steps-1) for spinner color (beige → green); tie to nervous_system startup. */
	public warmup(step: number): void {
		this.sendCommand("warmup", { step: Math.max(0, step) });
	}

	/** Cycle eye type (belly): uses pre-allocated buffer. */
	public cycleEyeType(): void {
		this.send(PAYLOAD_CYCLE_EYE_TYPE);
	}
}
