import { msg, substitute } from "../../../messages.js";
import type { MicStream } from "../hardware/mic_stream.js";

export class AuditoryCortex {
	private mic: MicStream;
	private onAudio: ((chunk: Buffer) => void) | null = null;

	constructor(mic: MicStream) {
		this.mic = mic;
	}

	public startListening(): void {
		if (this.onAudio) return;

		console.log(msg.hearing.cortex_starting);
		this.mic.start();

		this.onAudio = (chunk: Buffer) => {
			let peak = 0;
			for (let i = 0; i + 1 < chunk.length; i += 2) {
				const sample = chunk.readInt16LE(i);
				const abs = Math.abs(sample);
				if (abs > peak) peak = abs;
			}
			if (peak > 15000) {
				console.log(
					substitute(msg.hearing.loud_noise_detected, { peak: String(peak) }),
				);
			}
		};

		this.mic.on("audio", this.onAudio);
	}

	public stopListening(): void {
		if (this.onAudio) {
			this.mic.off("audio", this.onAudio);
			this.onAudio = null;
		}
		this.mic.stop();
	}
}
