import { EventEmitter } from "node:events";
import { msg, substitute } from "../../../messages.js";
import type { MicStream } from "../hardware/mic_stream.js";
import { detectWakeWord } from "./wake_keyword.js";

const RECORD_MS = Math.max(
	1000,
	Math.min(
		10000,
		parseInt(process.env.FURBACCA_WAKE_RECORD_MS ?? "3000", 10) || 3000,
	),
);

export class AuditoryCortex extends EventEmitter {
	private mic: MicStream;
	private onWake: (() => void) | null = null;
	private running = false;
	private loopTimeout: ReturnType<typeof setTimeout> | null = null;
	private chunkCount = 0;

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
			.catch((err) => {
				console.warn(
					substitute(msg.hearing.wake_check_failed, {
						message: String(err?.message ?? err),
					}),
				);
			})
			.finally(() => {
				if (!this.running) return;
				// No sleep between windows — eye sleep is handled elsewhere (e.g. motion timeout).
				this.loopTimeout = setTimeout(() => this.runLoop(), 0);
				this.loopTimeout?.unref?.();
			});
	}

	private async recordAndCheck(): Promise<void> {
		const pcm = await this.mic.recordChunk(RECORD_MS);
		if (!this.running) return;
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
		const woke = await detectWakeWord(pcm);
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
	}
}
