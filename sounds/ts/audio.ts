/**
 * Non-blocking WAV playback via aplay (ALSA) to I2S DAC.
 *
 * Hardware: MAX98357A I2S amp on Raspberry Pi — BCM 18 (BCLK), 19 (LRC), 21 (DIN).
 * Speaker: Two 8 Ω 1W in parallel → 4 Ω, 2W total. Software + ALSA capped at 60%
 * max gain so we stay within 2W and avoid TP4056 overheating.
 *
 * Does not block the event loop; suitable for use from touch handlers.
 */
import { execSync, spawn } from "child_process";
import fs from "fs";
import path from "path";
import { msg, substitute } from "../../messages.js";

// WAV files next to compiled code: dist/sounds/assets/ (so copy sounds/assets/ into dist or build step)
const SOUNDS_DIR = path.join(__dirname, "..", "assets");

/** ALSA card index for I2S DAC (default 0). Override with FURBACCA_AUDIO_CARD. */
const AUDIO_CARD = process.env.FURBACCA_AUDIO_CARD ?? "0";

/**
 * Max gain (0–1) applied to PCM before playback. Default 0.6 (60%) for 4 Ω parallel pair
 * (2W total); keeps power within speaker handling and avoids TP4056 overheating.
 * Override with FURBACCA_AUDIO_MAX_GAIN (e.g. 0.6).
 */
const MAX_GAIN = Math.max(0, Math.min(1, parseFloat(process.env.FURBACCA_AUDIO_MAX_GAIN ?? "0.6") || 0.6));

let volumeInitialized = false;
/** Skip starting another aplay while one is running (avoids device busy / exit 1 on rapid head touches). */
let currentPlayback: ReturnType<typeof spawn> | null = null;

/**
 * Set ALSA volume to 60% (hardware cap for 4 Ω 2W pair + TP4056). Runs once on first play.
 */
function setVolumeFor4Ohm2W(): void {
  if (volumeInitialized) return;
  volumeInitialized = true;
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
function parseWavHeader(buffer: Buffer): { sampleRate: number; channels: number; bitsPerSample: number; dataOffset: number; dataLength: number } | null {
  if (buffer.length < 44) return null;
  if (buffer.toString("ascii", 0, 4) !== "RIFF" || buffer.toString("ascii", 8, 12) !== "WAVE") return null;
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
    i += 8 + chunkSize;
  }
  if (sampleRate <= 0 || channels <= 0 || bitsPerSample !== 16 || dataLength <= 0) return null;
  return { sampleRate, channels, bitsPerSample, dataOffset, dataLength };
}

/**
 * Apply software volume limit to 16-bit PCM: multiply by MAX_GAIN and clamp.
 * Modifies buffer in place (only the range [dataOffset, dataOffset+dataLength)).
 */
function applyVolumeLimit(buffer: Buffer, dataOffset: number, dataLength: number): void {
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
 */
export function playWav(filename: string): void {
  if (currentPlayback !== null) return; // one at a time to avoid device busy (exit 1) on rapid touches
  setVolumeFor4Ohm2W();
  const filepath = path.join(SOUNDS_DIR, filename);
  let buffer: Buffer;
  try {
    buffer = fs.readFileSync(filepath);
  } catch (err) {
    console.error(substitute(msg.audio.aplay_failed, { message: (err as Error).message }));
    return;
  }
  const header = parseWavHeader(buffer);
  if (!header) {
    // Not 16-bit PCM or invalid WAV — fall back to direct aplay (no software limit)
    const fallbackChild = spawn("aplay", [filepath], { detached: true, stdio: "ignore" });
    currentPlayback = fallbackChild;
    fallbackChild.on("error", (err) => {
      currentPlayback = null;
      console.error(substitute(msg.audio.aplay_failed, { message: err.message }));
    });
    fallbackChild.on("exit", (code) => {
      currentPlayback = null;
      if (code !== 0 && code !== null) console.error(substitute(msg.audio.aplay_exit, { code: String(code) }));
    });
    fallbackChild.unref();
    return;
  }
  applyVolumeLimit(buffer, header.dataOffset, header.dataLength);
  const rawPcm = buffer.subarray(header.dataOffset, header.dataOffset + header.dataLength);
  const child = spawn(
    "aplay",
    ["-f", "S16_LE", "-r", String(header.sampleRate), "-c", String(header.channels), "-q"],
    { stdio: ["pipe", "ignore", "ignore"] }
  );
  currentPlayback = child;
  child.stdin?.on("error", () => {});
  child.stdin?.end(rawPcm);
  child.on("error", (err) => {
    currentPlayback = null;
    console.error(substitute(msg.audio.aplay_failed, { message: err.message }));
  });
  child.on("exit", (code) => {
    currentPlayback = null;
    if (code !== 0 && code !== null) console.error(substitute(msg.audio.aplay_exit, { code: String(code) }));
  });
  child.unref();
}

/**
 * Play the giggle sound (head touch). Non-blocking.
 */
export function playGiggle(): void {
  playWav("giggle.wav");
}

/**
 * Call once at startup if you want volume set before any play (e.g. from nervous_system).
 * Otherwise volume is set lazily on first playWav/playGiggle.
 */
export function initAudio(): void {
  setVolumeFor4Ohm2W();
}
