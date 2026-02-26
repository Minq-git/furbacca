import { type ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import { EventEmitter } from "node:events";

import { msg, substitute } from "../../../messages.js";

export class MicStream extends EventEmitter {
	public readonly card: string;
	private proc: ChildProcessWithoutNullStreams | null = null;

	constructor(card: string = "0") {
		super();
		this.card = card;
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
