/**
 * Non-blocking WAV playback via aplay (ALSA) to I2S DAC.
 *
 * Hardware: MAX98357A I2S amp on Raspberry Pi — BCM 18 (BCLK), 19 (LRC), 21 (DIN).
 * Speaker: 18.9 Ω (expect lower volume than 4/8 Ω). Volume is set to 50% at first
 * use to protect the TP4056 power rail during bench test.
 *
 * Does not block the event loop; suitable for use from touch handlers without
 * blocking eyes physics or fan monitoring.
 */
import { execSync, spawn } from "child_process";
import path from "path";
import { msg, substitute } from "../../messages.js";

// WAV files next to compiled code: dist/sounds/assets/ (so copy sounds/assets/ into dist or build step)
const SOUNDS_DIR = path.join(__dirname, "..", "assets");

/** ALSA card index for I2S DAC (default 0). Override with FURBACCA_AUDIO_CARD. */
const AUDIO_CARD = process.env.FURBACCA_AUDIO_CARD ?? "0";

let volumeInitialized = false;
/** Skip starting another aplay while one is running (avoids device busy / exit 1 on rapid head touches). */
let currentPlayback: ReturnType<typeof spawn> | null = null;

/**
 * Set playback volume to 50% for bench safety (TP4056 / 18.9 Ω speaker).
 * Runs once on first play. Uses amixer -c N set PCM 50% (or Master if PCM missing).
 */
function setVolume50(): void {
  if (volumeInitialized) return;
  volumeInitialized = true;
  const controls = ["PCM", "Master", "Playback", "Digital"];
  for (const name of controls) {
    try {
      execSync(`amixer -c ${AUDIO_CARD} set ${name} 50%`, { stdio: "ignore" });
      console.log(msg.audio.volume_set_50);
      return;
    } catch {
      /* try next */
    }
  }
  // MAX98357A and many I2S DACs have no hardware volume; playback still works at fixed level
  console.log(msg.audio.volume_no_control);
}

/**
 * Play a WAV file immediately in the background. Returns without waiting for playback to finish.
 * Uses aplay (ALSA) for low-latency output to I2S DAC (e.g. MAX98357A).
 * Volume is set to 50% on first use.
 */
export function playWav(filename: string): void {
  if (currentPlayback !== null) return; // one at a time to avoid device busy (exit 1) on rapid touches
  setVolume50();
  const filepath = path.join(SOUNDS_DIR, filename);
  const child = spawn("aplay", [filepath], {
    detached: true,
    stdio: "ignore",
  });
  currentPlayback = child;
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
  setVolume50();
}
