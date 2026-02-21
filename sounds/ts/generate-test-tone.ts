/**
 * Generate a test tone WAV for checking frequency response of 1W 8Ω micro speakers.
 * Output: sounds/assets/test_tone_1w8ohm.wav
 * Run from repo root: npx ts-node sounds/ts/generate-test-tone.ts  (or node dist/sounds/ts/generate-test-tone.js after build)
 *
 * Tone: 100, 250, 500, 1000, 2000, 3000, 4000 Hz, 0.5s each with 0.1s silence between.
 * 44.1 kHz, 16-bit mono. Amplitude 0.3 (safe for small drivers; software limiter applies on playback).
 */
import fs from "fs";
import path from "path";

const SAMPLE_RATE = 44100;
const BITS_PER_SAMPLE = 16;
const CHANNELS = 1;
const AMPLITUDE = 0.3; // fraction of full scale; limiter will cap on playback
const TONE_DURATION_S = 0.5;
const SILENCE_DURATION_S = 0.1;

const FREQUENCIES_HZ = [100, 250, 500, 1000, 2000, 3000, 4000];

function writeWavHeader(
  dataLength: number,
  sampleRate: number,
  channels: number,
  bitsPerSample: number
): Buffer {
  const byteRate = sampleRate * channels * (bitsPerSample >>> 3);
  const blockAlign = channels * (bitsPerSample >>> 3);
  const header = Buffer.alloc(44);
  let offset = 0;
  header.write("RIFF", offset); offset += 4;
  header.writeUInt32LE(36 + dataLength, offset); offset += 4;
  header.write("WAVE", offset); offset += 4;
  header.write("fmt ", offset); offset += 4;
  header.writeUInt32LE(16, offset); offset += 4; // fmt chunk size
  header.writeUInt16LE(1, offset); offset += 2;   // PCM
  header.writeUInt16LE(channels, offset); offset += 2;
  header.writeUInt32LE(sampleRate, offset); offset += 4;
  header.writeUInt32LE(byteRate, offset); offset += 4;
  header.writeUInt16LE(blockAlign, offset); offset += 2;
  header.writeUInt16LE(bitsPerSample, offset); offset += 2;
  header.write("data", offset); offset += 4;
  header.writeUInt32LE(dataLength, offset);
  return header;
}

function generateSine(freqHz: number, durationS: number, sampleRate: number, amplitude: number): Int16Array {
  const numSamples = Math.floor(durationS * sampleRate);
  const out = new Int16Array(numSamples);
  const twoPiF = (2 * Math.PI * freqHz) / sampleRate;
  const scale = amplitude * 32767;
  for (let i = 0; i < numSamples; i++) {
    out[i] = Math.round(scale * Math.sin(twoPiF * i));
  }
  return out;
}

function generateSilence(durationS: number, sampleRate: number): Int16Array {
  const numSamples = Math.floor(durationS * sampleRate);
  return new Int16Array(numSamples);
}

function main(): void {
  const repoRoot = process.cwd();
  const assetsDir = path.join(repoRoot, "sounds", "assets");
  const outPath = path.join(assetsDir, "test_tone_1w8ohm.wav");

  const chunks: Int16Array[] = [];
  for (let i = 0; i < FREQUENCIES_HZ.length; i++) {
    chunks.push(generateSine(FREQUENCIES_HZ[i]!, TONE_DURATION_S, SAMPLE_RATE, AMPLITUDE));
    if (i < FREQUENCIES_HZ.length - 1) {
      chunks.push(generateSilence(SILENCE_DURATION_S, SAMPLE_RATE));
    }
  }
  const totalSamples = chunks.reduce((sum, c) => sum + c.length, 0);
  const dataLength = totalSamples * 2; // 16-bit = 2 bytes per sample
  const data = Buffer.alloc(dataLength);
  let offset = 0;
  for (const chunk of chunks) {
    for (let i = 0; i < chunk.length; i++) {
      data.writeInt16LE(chunk[i]!, offset);
      offset += 2;
    }
  }
  const header = writeWavHeader(dataLength, SAMPLE_RATE, CHANNELS, BITS_PER_SAMPLE);
  if (!fs.existsSync(assetsDir)) {
    fs.mkdirSync(assetsDir, { recursive: true });
  }
  fs.writeFileSync(outPath, Buffer.concat([header, data]));
  console.log(`Wrote ${outPath}`);
  console.log(`Frequencies: ${FREQUENCIES_HZ.join(", ")} Hz; ${TONE_DURATION_S}s each, ${SILENCE_DURATION_S}s silence.`);
}

main();
