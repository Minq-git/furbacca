/**
 * Non-blocking WAV playback via aplay (ALSA).
 * Does not block the event loop; suitable for use from touch handlers
 * without blocking eyes physics or fan monitoring.
 */
import { spawn } from "child_process";
import path from "path";
import { msg, substitute } from "../../messages.js";

// WAV files live in sounds/assets/; path works via ts-node or node dist/...
const SOUNDS_DIR = path.join(__dirname, "..", "assets");

/**
 * Play a WAV file immediately in the background. Returns without waiting for playback to finish.
 * Uses aplay (ALSA) for low-latency output to I2S DAC (e.g. MAX98357A).
 */
export function playWav(filename: string): void {
  const filepath = path.join(SOUNDS_DIR, filename);
  const child = spawn("aplay", [filepath], {
    detached: true,
    stdio: "ignore",
  });
  child.on("error", (err) => {
    console.error(substitute(msg.audio.aplay_failed, { message: err.message }));
  });
  child.unref();
}

/**
 * Play the giggle sound (head touch). Non-blocking.
 */
export function playGiggle(): void {
  playWav("giggle.wav");
}
