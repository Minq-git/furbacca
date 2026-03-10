/**
 * Non-blocking WAV playback via aplay (ALSA) to I2S DAC.
 *
 * Hardware: MAX98357A I2S amp on Raspberry Pi — BCM 18 (BCLK), 19 (LRC), 21 (DIN).
 * Speaker: Two 8 Ω 1W in parallel → 4 Ω, 2W total. Software + ALSA capped at 60%
 * max gain so we stay within 2W and avoid TP4056 overheating.
 *
 * Does not block the event loop; suitable for use from touch handlers.
 */
import { execSync, spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { msg, substitute } from "../../messages.js";

// Prefer dist/voice/assets/ (next to compiled code). Fallback: repo root voice/assets/ if sync-sounds wasn't run.
const DIST_VOICE_ASSETS = path.join(__dirname, "..", "assets");

/** ALSA card index for I2S DAC (default 0). Override with FURBACCA_AUDIO_CARD. */
const AUDIO_CARD = process.env.FURBACCA_AUDIO_CARD ?? "0";
/** Force I2S device so playback doesn't go to HDMI (default). */
const APLAY_DEVICE = `plughw:${AUDIO_CARD},0`;

/**
 * Max gain (0–1) applied to PCM before playback. Default 0.6 (60%) for 4 Ω parallel pair
 * (2W total); keeps power within speaker handling and avoids TP4056 overheating.
 * Override with FURBACCA_AUDIO_MAX_GAIN (e.g. 0.6).
 */
const MAX_GAIN = Math.max(
	0,
	Math.min(1, parseFloat(process.env.FURBACCA_AUDIO_MAX_GAIN ?? "0.6") || 0.6),
);

let volumeInitialized = false;
/** Throttle repeated aplay exit warnings (e.g. device open failure) to at most once per 30s. */
const APLAY_EXIT_WARN_INTERVAL_MS = 30_000;
let lastAplayExitWarnTime = 0;
/** Persistent aplay process: kept open to avoid start/stop clicks; format may change between files. */
let persistentAplay: ReturnType<typeof spawn> | null = null;
/** Format the current persistent pipe was started with (so we restart if next WAV differs). */
let persistentAplayFormat: { sampleRate: number; channels: number } | null =
	null;

/**
 * Set ALSA volume to 60% (hardware cap for 4 Ω 2W pair + TP4056). Runs once on first play.
 * Skip if FURBACCA_SKIP_AMIXER=1 (e.g. if amixer puts I2S in a bad state after wake-furbacca).
 */
function setVolumeFor4Ohm2W(): void {
	if (volumeInitialized) return;
	volumeInitialized = true;
	if (process.env.FURBACCA_SKIP_AMIXER === "1") {
		console.log(msg.audio.volume_no_control);
		return;
	}
	const controls = ["PCM", "Master", "Playback", "Digital"];
	for (const name of controls) {
		try {
			execSync(`amixer -c ${AUDIO_CARD} set ${name} 60%`, { stdio: "ignore" });
			console.log(msg.audio.volume_set_4ohm_2w);
			return;
		} catch {
			/* try next */
		}
	}
	// MAX98357A and many I2S DACs have no hardware volume; software limiter still applies
	console.log(msg.audio.volume_no_control);
}

/** Minimal WAV parse: find fmt and data chunks, return { sampleRate, channels, bitsPerSample, dataOffset, dataLength } or null. */
function parseWavHeader(buffer: Buffer): {
	sampleRate: number;
	channels: number;
	bitsPerSample: number;
	dataOffset: number;
	dataLength: number;
} | null {
	if (buffer.length < 44) return null;
	if (
		buffer.toString("ascii", 0, 4) !== "RIFF" ||
		buffer.toString("ascii", 8, 12) !== "WAVE"
	)
		return null;
	let i = 12;
	let sampleRate = 0;
	let channels = 0;
	let bitsPerSample = 0;
	let dataOffset = 0;
	let dataLength = 0;
	while (i + 8 <= buffer.length) {
		const chunkId = buffer.toString("ascii", i, i + 4);
		const chunkSize = buffer.readUInt32LE(i + 4);
		if (chunkId === "fmt ") {
			if (chunkSize >= 16) {
				const format = buffer.readUInt16LE(i + 8);
				if (format !== 1) return null; // PCM only
				channels = buffer.readUInt16LE(i + 10);
				sampleRate = buffer.readUInt32LE(i + 12);
				bitsPerSample = buffer.readUInt16LE(i + 22);
			}
		} else if (chunkId === "data") {
			dataOffset = i + 8;
			dataLength = chunkSize;
		}
		// RIFF chunks are word-aligned; skip padding byte when chunk size is odd
		i += 8 + chunkSize + (chunkSize & 1);
	}
	if (
		sampleRate <= 0 ||
		channels <= 0 ||
		bitsPerSample !== 16 ||
		dataLength <= 0
	)
		return null;
	return { sampleRate, channels, bitsPerSample, dataOffset, dataLength };
}

/**
 * Apply software volume limit to 16-bit PCM: multiply by MAX_GAIN and clamp.
 * Modifies buffer in place (only the range [dataOffset, dataOffset+dataLength)).
 */
function applyVolumeLimit(
	buffer: Buffer,
	dataOffset: number,
	dataLength: number,
): void {
	const numSamples = dataLength >>> 1;
	for (let i = 0; i < numSamples; i++) {
		const idx = dataOffset + i * 2;
		const sample = buffer.readInt16LE(idx);
		const limited = Math.round(sample * MAX_GAIN);
		const clamped = Math.max(-32767, Math.min(32767, limited));
		buffer.writeInt16LE(clamped, idx);
	}
}

/**
 * Play a WAV file with software volume limiter (1W 8Ω safe). Returns without waiting for playback to finish.
 * Parses WAV, applies MAX_GAIN to PCM, pipes raw S16_LE to aplay. Falls back to direct aplay if not 16-bit PCM.
 * @param maxDurationSeconds - if set, only play this many seconds (16-bit pipe path only; fallback plays full file)
 */
/** Resolve WAV path: dist/voice/assets first, then repo root voice/assets (if sync-sounds wasn't run). */
function resolveSoundPath(filename: string): string {
	const distPath = path.join(DIST_VOICE_ASSETS, filename);
	if (fs.existsSync(distPath)) return distPath;
	const repoPath = path.join(process.cwd(), "voice", "assets", filename);
	return fs.existsSync(repoPath) ? repoPath : distPath; // try dist first; fallback repo; else return dist for clear error
}

function startPersistentAplay(sampleRate: number, channels: number): void {
	if (persistentAplay && !persistentAplay.killed) persistentAplay.kill();
	persistentAplay = spawn(
		"aplay",
		[
			"-D",
			APLAY_DEVICE,
			"-f",
			"S16_LE",
			"-r",
			String(sampleRate),
			"-c",
			String(channels),
			"-q",
		],
		{ stdio: ["pipe", "ignore", "ignore"] },
	);
	persistentAplayFormat = { sampleRate, channels };
	persistentAplay.stdin?.on("error", () => {
		if (persistentAplay) {
			persistentAplay = null;
			persistentAplayFormat = null;
		}
	});
	persistentAplay.on("error", (err) => {
		console.error(substitute(msg.audio.aplay_failed, { message: err.message }));
		persistentAplay = null;
		persistentAplayFormat = null;
	});
	persistentAplay.on("exit", (code) => {
		persistentAplay = null;
		persistentAplayFormat = null;
		// aplay often exits 1 after playing stdin data (stream done); playback still succeeded. Only log other failures.
		if (code !== 0 && code !== 1 && code !== null) {
			const now = Date.now();
			if (now - lastAplayExitWarnTime >= APLAY_EXIT_WARN_INTERVAL_MS) {
				lastAplayExitWarnTime = now;
				console.error(substitute(msg.audio.aplay_exit, { code: String(code) }));
			}
		}
	});
	persistentAplay.unref();
}

export function playWav(filename: string, maxDurationSeconds?: number): void {
	setVolumeFor4Ohm2W();
	const filepath = resolveSoundPath(filename);
	let buffer: Buffer;
	try {
		buffer = fs.readFileSync(filepath);
	} catch (err) {
		console.error(
			substitute(msg.audio.aplay_failed, { message: (err as Error).message }),
		);
		return;
	}
	const header = parseWavHeader(buffer);
	if (!header) {
		// Not 16-bit PCM or invalid WAV — fall back to direct aplay (no software limit).
		const args = ["-D", APLAY_DEVICE, "-q"];
		if (maxDurationSeconds != null && maxDurationSeconds > 0) {
			args.push("-d", String(Math.round(maxDurationSeconds)));
		}
		args.push(filepath);
		const fallbackChild = spawn("aplay", args, {
			detached: true,
			stdio: "ignore",
		});
		fallbackChild.on("error", (err) => {
			console.error(
				substitute(msg.audio.aplay_failed, { message: err.message }),
			);
		});
		fallbackChild.on("exit", (code) => {
			if (code !== 0 && code !== null) {
				const now = Date.now();
				if (now - lastAplayExitWarnTime >= APLAY_EXIT_WARN_INTERVAL_MS) {
					lastAplayExitWarnTime = now;
					console.error(substitute(msg.audio.aplay_exit, { code: String(code) }));
				}
			}
		});
		fallbackChild.unref();
		return;
	}
	const bytesPerSample = 2;
	const maxBytes =
		maxDurationSeconds != null && maxDurationSeconds > 0
			? Math.min(
					header.dataLength,
					Math.floor(header.sampleRate * header.channels * maxDurationSeconds) *
						bytesPerSample,
				)
			: header.dataLength;
	// Start or restart persistent aplay if needed (missing or format changed).
	const needFormat = {
		sampleRate: header.sampleRate,
		channels: header.channels,
	};
	if (
		!persistentAplay ||
		persistentAplay.killed ||
		!persistentAplayFormat ||
		persistentAplayFormat.sampleRate !== needFormat.sampleRate ||
		persistentAplayFormat.channels !== needFormat.channels
	) {
		startPersistentAplay(needFormat.sampleRate, needFormat.channels);
	}
	applyVolumeLimit(buffer, header.dataOffset, maxBytes);
	const rawPcm = buffer.subarray(
		header.dataOffset,
		header.dataOffset + maxBytes,
	);
	try {
		persistentAplay?.stdin?.write(rawPcm);
	} catch {
		persistentAplay = null;
		persistentAplayFormat = null;
	}
}

/**
 * Play the giggle sound. Plays first 2 seconds only.
 */
export function playGiggle(): void {
	playWav("giggle.wav", 2);
}

/**
 * Play the purr (pet) sound. Plays first 3 seconds only.
 */
export function playPurr(): void {
	playWav("pet.wav", 3);
}

/**
 * Call once at startup if you want volume set before any play (e.g. from nervous_system).
 * Otherwise volume is set lazily on first playWav/playGiggle.
 */
export function initAudio(): void {
	setVolumeFor4Ohm2W();
}
