import { EventEmitter } from "node:events";
import { msg } from "../../../messages.js";
import type { MicStream } from "../hardware/mic_stream.js";
import { detectWakeWord } from "./wake_keyword.js";

const RECORD_MS = Math.max(
	1000,
	Math.min(
		10000,
		parseInt(process.env.FURBACCA_WAKE_RECORD_MS ?? "3000", 10) || 3000,
	),
);
const PAUSE_MS = Math.max(
	500,
	Math.min(
		10000,
		parseInt(process.env.FURBACCA_WAKE_PAUSE_MS ?? "2000", 10) || 2000,
	),
);

export class AuditoryCortex extends EventEmitter {
	private mic: MicStream;
	private onWake: (() => void) | null = null;
	private running = false;
	private loopTimeout: ReturnType<typeof setTimeout> | null = null;

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
		console.log(msg.hearing.cortex_starting);
		this.runLoop();
	}

	private runLoop(): void {
		if (!this.running) return;
		this.recordAndCheck()
			.catch(() => {})
			.finally(() => {
				if (!this.running) return;
				this.loopTimeout = setTimeout(() => this.runLoop(), PAUSE_MS);
				this.loopTimeout?.unref?.();
			});
	}

	private async recordAndCheck(): Promise<void> {
		const pcm = await this.mic.recordChunk(RECORD_MS);
		if (!this.running || !pcm.length) return;
		const woke = await detectWakeWord(pcm);
		if (woke) {
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
	}
}
