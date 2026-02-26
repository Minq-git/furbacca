import { type ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import { EventEmitter } from "node:events";

import { msg, substitute } from "../../../messages.js";

/** Format for recordChunk (Vosk expects 16 kHz mono S16_LE). */
export const RECORD_CHUNK_RATE = 16000;
export const RECORD_CHUNK_CHANNELS = 1;

export class MicStream extends EventEmitter {
	public readonly card: string;
	private proc: ChildProcessWithoutNullStreams | null = null;

	constructor(card: string = "0") {
		super();
		this.card = card;
	}

	/**
	 * Record for a fixed duration then stop. No persistent stream — avoids ALSA overruns.
	 * Returns raw S16_LE 16 kHz mono PCM.
	 */
	public recordChunk(ms: number): Promise<Buffer> {
		return new Promise((resolve, reject) => {
			const durationSec = Math.max(0.1, Math.min(30, ms / 1000));
			const args = [
				"-D",
				`plughw:${this.card},0`,
				"-f",
				"S16_LE",
				"-r",
				String(RECORD_CHUNK_RATE),
				"-c",
				String(RECORD_CHUNK_CHANNELS),
				"-d",
				String(durationSec),
				"-q",
			];
			const child = spawn("arecord", args, {
				stdio: ["ignore", "pipe", "pipe"],
			});
			const chunks: Buffer[] = [];
			child.stdout?.on("data", (c: Buffer) => chunks.push(c));
			child.stderr?.on("data", (data: Buffer) => {
				const line = data.toString("utf8").trim();
				if (line)
					console.error(substitute(msg.hearing.alsa_error, { message: line }));
			});
			child.on("error", (err) => reject(err));
			child.on("exit", (code) => {
				if (code === 0) resolve(Buffer.concat(chunks));
				else reject(new Error(`arecord exited ${code}`));
			});
		});
	}

	public start(): void {
		if (this.proc) return;

		console.log(substitute(msg.hearing.mic_initializing, { card: this.card }));
		const args = [
			"-D",
			`plughw:${this.card},0`,
			"-f",
			"S32_LE",
			"-r",
			"16000",
			"-c",
			"1",
			"-q",
		];

		const child = spawn("arecord", args, {
			stdio: ["pipe", "pipe", "pipe"],
		});
		this.proc = child;

		child.stdout.on("data", (chunk) => {
			this.emit("audio", chunk as Buffer);
		});

		child.stderr.on("data", (data) => {
			const line = data.toString("utf8").trim();
			if (line)
				console.error(substitute(msg.hearing.alsa_error, { message: line }));
		});

		child.on("error", (err) => {
			console.error(
				substitute(msg.hearing.arecord_failed, { message: err.message }),
			);
			this.proc = null;
		});

		child.on("exit", (code, signal) => {
			if (this.proc === child) this.proc = null;
			if (code !== 0 && code !== null) {
				console.error(
					substitute(msg.hearing.arecord_exit, { code: String(code) }),
				);
				if (code === 1) {
					console.error(msg.hearing.arecord_no_device_hint);
				}
			} else if (signal) {
				console.log(
					substitute(msg.hearing.arecord_stopped, { signal: String(signal) }),
				);
			}
		});
	}

	public stop(): void {
		const child = this.proc;
		this.proc = null;
		if (!child) return;

		console.log(msg.hearing.mic_stopping);
		child.kill("SIGTERM");
		const t = setTimeout(() => {
			try {
				child.kill("SIGKILL");
			} catch {
				/* ignore */
			}
		}, 1000);
		t.unref?.();
	}
}
