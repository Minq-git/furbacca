import { execSync } from "node:child_process";
import { EventEmitter } from "node:events";
import { msg, substitute } from "../../../messages.js";
import type { MicStream } from "../hardware/mic_stream.js";
import { createWakeDetector } from "./wake_keyword.js";

/** Return true if the given ALSA card number has a capture device (from arecord -l). */
function cardHasCapture(card: string): boolean {
	try {
		const out = execSync("arecord -l", {
			encoding: "utf8",
			stdio: ["ignore", "pipe", "ignore"],
		});
		const captureSection = out.split("CAPTURE Hardware Devices")[1] ?? "";
		return new RegExp(`card\\s+${card}\\s*:`).test(captureSection);
	} catch {
		return false;
	}
}

const RECORD_MS = Math.max(
	1000,
	Math.min(
		10000,
		parseInt(process.env.FURBACCA_WAKE_RECORD_MS ?? "3000", 10) || 3000,
	),
);

/** Throttle repeated "wake check failed" logs when mic/card missing (max once per 30s). */
const WAKE_CHECK_WARN_INTERVAL_MS = 30_000;
let lastWakeCheckWarnTime = 0;

/** After this many consecutive record failures, wait BACKOFF_MS before retrying (stops log flood when no mic). */
const CONSECUTIVE_FAILURES_BEFORE_BACKOFF = 5;
const BACKOFF_MS = 60_000;

export class AuditoryCortex extends EventEmitter {
	private mic: MicStream;
	private onWake: (() => void) | null = null;
	private running = false;
	private loopTimeout: ReturnType<typeof setTimeout> | null = null;
	private chunkCount = 0;
	private consecutiveFailures = 0;
	private wakeDetector: ReturnType<typeof createWakeDetector> | null = null;

	constructor(mic: MicStream) {
		super();
		this.mic = mic;
	}

	public setOnWake(cb: () => void): void {
		this.onWake = cb;
	}

	public startListening(): void {
		if (this.running) return;
		this.running = true;
		this.wakeDetector = createWakeDetector();
		console.log(msg.hearing.cortex_starting);
		if (!cardHasCapture(this.mic.card)) {
			console.log(
				substitute(msg.hearing.capture_card_hint, { card: this.mic.card }),
			);
		}
		this.runLoop();
	}

	private runLoop(): void {
		if (!this.running) return;
		this.recordAndCheck()
			.catch((err) => {
				this.consecutiveFailures++;
				const now = Date.now();
				if (now - lastWakeCheckWarnTime >= WAKE_CHECK_WARN_INTERVAL_MS) {
					lastWakeCheckWarnTime = now;
					console.warn(
						substitute(msg.hearing.wake_check_failed, {
							message: String(err?.message ?? err),
						}),
					);
				}
			})
			.finally(() => {
				if (!this.running) return;
				const delay =
					this.consecutiveFailures >= CONSECUTIVE_FAILURES_BEFORE_BACKOFF
						? (() => {
								if (this.consecutiveFailures === CONSECUTIVE_FAILURES_BEFORE_BACKOFF) {
									console.log(msg.hearing.backoff_no_device);
								}
								return BACKOFF_MS;
							})()
						: 0;
				this.loopTimeout = setTimeout(() => this.runLoop(), delay);
				this.loopTimeout?.unref?.();
			});
	}

	private async recordAndCheck(): Promise<void> {
		const pcm = await this.mic.recordChunk(RECORD_MS);
		if (!this.running) return;
		this.consecutiveFailures = 0; // success
		this.chunkCount++;
		if (!pcm.length) {
			if (this.chunkCount % 10 === 1) {
				console.warn(msg.hearing.no_audio_chunk);
			}
			return;
		}
		if (this.chunkCount % 20 === 1) {
			console.log(
				substitute(msg.hearing.listening_heartbeat, {
					n: String(this.chunkCount),
					bytes: String(pcm.length),
				}),
			);
		}
		if (!this.wakeDetector) return;
		const woke = await this.wakeDetector.checkChunk(pcm);
		if (woke) {
			console.log(msg.hearing.wake_word_triggered);
			console.log(msg.hearing.wake_detected);
			this.emit("wake");
			this.onWake?.();
		}
	}

	public stopListening(): void {
		this.running = false;
		if (this.loopTimeout) {
			clearTimeout(this.loopTimeout);
			this.loopTimeout = null;
		}
		this.wakeDetector?.close();
		this.wakeDetector = null;
	}
}
