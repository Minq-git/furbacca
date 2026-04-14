import { spawn } from "node:child_process";
import path from "node:path";

import { msg, substitute } from "../../../messages.js";
import { monitorMotion } from "../../../senses/motion.js";
import {
	type TouchCallback,
	type TouchSenses,
	type TouchSensor,
	VIBE_BCM,
} from "../../../senses/touch";
import type { EyeBridge } from "../../../vision/ts/eye_bridge.js";

let initAudio: () => void = () => {};
let playWav: (filename: string, maxDurationSeconds?: number) => void = () => {};
try {
	// eslint-disable-next-line @typescript-eslint/no-require-imports
	const audio = require("../../../voice/ts/audio.js");
	initAudio = audio.initAudio;
	playWav = audio.playWav;
	console.log(msg.audio.module_loaded);
} catch {
	console.warn(msg.audio.module_not_found);
}

export type MatterTouchSink = {
	notifyTouch(sensor: TouchSensor, active: boolean): void;
};

export type ReflexesConfig = {
	openThenLookMs: number;
	motionSleepMs: number;
	motionClearDebounceMs: number;
	sleepCloseDurationS: number;
};

export class Reflexes {
	private eyes: EyeBridge;
	private touch: TouchSenses;
	private matter: MatterTouchSink | null;
	private cfg: ReflexesConfig;

	// Touch state
	private headActive = false;
	private bellyActive = false;

	// --- DEBOUNCE TRACKING ---
	// Prevents rapid-fire "ghost touches" from electrical noise
	private lastTouchTimes: Record<string, number> = {
		head: 0,
		belly: 0,
		shiver: 0,
	};
	private readonly TOUCH_COOLDOWN_MS = 1500;

	/**
	 * Holds:
	 * - Head + belly: 5s = eyes re-init
	 * - Belly only: 15s = network heal
	 * - Head + belly: 30s = system halt (immediate)
	 */
	private readonly HEAD_BELLY_HOLD_MS = 5000;
	private readonly BELLY_HEAL_HOLD_MS = 15000;
	private readonly HEAD_BELLY_SHUTDOWN_HOLD_MS = 30000;
	private headBellyHoldTimer: ReturnType<typeof setTimeout> | null = null;
	private headBellyShutdownTimer: ReturnType<typeof setTimeout> | null = null;
	private bellyHealTimer: ReturnType<typeof setTimeout> | null = null;
	private headBellyHoldCooldown = false;
	private bellyHealCooldown = false;

	// Motion state
	private motionSleepTimer: ReturnType<typeof setTimeout> | null = null;
	private motionClearDebounceTimer: ReturnType<typeof setTimeout> | null = null;
	private warmupComplete = false;
	private motionWasAsleep = false;
	private motionFirstDetectedLogged = false;
	private motionFirstDetectedPendingLog = false;

	// Watches
	private stopTouchWatch: (() => Promise<void>) | null = null;
	private stopMotionWatch: (() => Promise<void>) | null = null;
	private pollInterval: ReturnType<typeof setInterval> | null = null;

	/** If set (e.g. 0x60), belly touch runs chip-tool onoff on <nodeId> <endpoint>. Requires chip-tool. */
	private chipToolNodeId = process.env.CHIP_TOOL_NODE_ID?.trim() || undefined;
	private chipToolEndpoint = process.env.CHIP_TOOL_ENDPOINT ?? "0x1";

	constructor(
		eyes: EyeBridge,
		touch: TouchSenses,
		config: ReflexesConfig,
		matter: MatterTouchSink | null = null,
	) {
		this.eyes = eyes;
		this.touch = touch;
		this.cfg = config;
		this.matter = matter;
	}

	public startListening(): {
		usingTouchEvents: boolean;
		usingMotionEvents: boolean;
	} {
		initAudio(); // set ALSA volume once at startup (or no-op if not available / FURBACCA_SKIP_AMIXER=1)

		if (this.stopTouchWatch || this.pollInterval || this.stopMotionWatch) {
			return {
				usingTouchEvents: this.stopTouchWatch !== null,
				usingMotionEvents: this.stopMotionWatch !== null,
			};
		}

		const onTouch: TouchCallback = (sensor, active) =>
			this.onTouch(sensor, active);
		this.stopTouchWatch = this.touch.startEventWatch(onTouch);
		if (!this.stopTouchWatch) {
			this.pollInterval = setInterval(() => this.touch.poll(onTouch), 20);
		}

		this.stopMotionWatch = monitorMotion((detected) => this.onMotion(detected));

		return {
			usingTouchEvents: this.stopTouchWatch !== null,
			usingMotionEvents: this.stopMotionWatch !== null,
		};
	}

	public async stopListening(): Promise<void> {
		if (this.headBellyHoldTimer !== null) {
			clearTimeout(this.headBellyHoldTimer);
			this.headBellyHoldTimer = null;
		}
		if (this.headBellyShutdownTimer !== null) {
			clearTimeout(this.headBellyShutdownTimer);
			this.headBellyShutdownTimer = null;
		}
		if (this.bellyHealTimer !== null) {
			clearTimeout(this.bellyHealTimer);
			this.bellyHealTimer = null;
		}
		if (this.motionClearDebounceTimer !== null) {
			clearTimeout(this.motionClearDebounceTimer);
			this.motionClearDebounceTimer = null;
		}
		if (this.motionSleepTimer !== null) {
			clearTimeout(this.motionSleepTimer);
			this.motionSleepTimer = null;
		}
		if (this.pollInterval !== null) {
			clearInterval(this.pollInterval);
			this.pollInterval = null;
		}

		const stopTouch = this.stopTouchWatch;
		this.stopTouchWatch = null;
		const stopMotion = this.stopMotionWatch;
		this.stopMotionWatch = null;

		await Promise.all([
			stopTouch ? stopTouch() : Promise.resolve(),
			stopMotion ? stopMotion() : Promise.resolve(),
		]);
	}

	public setMatter(matter: MatterTouchSink | null): void {
		this.matter = matter;
	}

	public markWarmupComplete(): void {
		this.warmupComplete = true;
		if (this.motionFirstDetectedPendingLog) {
			this.motionFirstDetectedPendingLog = false;
			this.motionFirstDetectedLogged = true;
			console.log(msg.nervous_system.motion_sensor_triggered);
		}
	}

	private chipToolOn(): void {
		if (!this.chipToolNodeId) return;
		const child = spawn(
			"chip-tool",
			["onoff", "on", this.chipToolNodeId, this.chipToolEndpoint],
			{
				stdio: "ignore",
				detached: true,
			},
		);
		child.unref();
	}

	private handleBellyTouch(): void {
		console.log(msg.nervous_system.belly_cycling);
		console.log(msg.audio.giggle_playing);
		playWav("giggle.wav", 2);
		this.eyes.cycleEyeType();
		this.eyes.sendCommand("look", { x: 0, y: 0, pupil_mode: "wide" });
		this.chipToolOn();
	}

	private onTouch(sensor: TouchSensor, active: boolean): void {
		// Update hardware state instantly (needed for hold timers)
		if (sensor === "head") this.headActive = active;
		else if (sensor === "belly") this.bellyActive = active;

		this.matter?.notifyTouch(sensor, active);

		// Holds: head+belly combos and belly-only heal
		if (sensor === "head" || sensor === "belly") {
			// Belly-only: 15s → network heal
			if (!this.headActive && this.bellyActive) {
				if (this.bellyHealTimer === null && !this.bellyHealCooldown) {
					this.bellyHealTimer = setTimeout(() => {
						this.bellyHealTimer = null;
						this.bellyHealCooldown = true;
						console.log(msg.nervous_system.network_heal_trigger);
						playWav("nggyu.wav", 18);
						this.eyes.sendCommand("set_eye_type", { type: "demon" });
						const scriptPath = path.join(
							process.cwd(),
							".scripts",
							"diagnostics",
							"heal-network.sh",
						);
						const child = spawn("bash", [scriptPath], {
							detached: true,
							stdio: "ignore",
						});
						child.unref();
					}, this.BELLY_HEAL_HOLD_MS);
				}
			} else {
				if (this.bellyHealTimer !== null) {
					clearTimeout(this.bellyHealTimer);
					this.bellyHealTimer = null;
				}
				if (!this.bellyActive) this.bellyHealCooldown = false;
			}

			// Head + belly: 5s → eyes re-init; 30s → halt
			if (!this.headActive || !this.bellyActive) {
				if (this.headBellyHoldTimer !== null) {
					clearTimeout(this.headBellyHoldTimer);
					this.headBellyHoldTimer = null;
				}
				if (this.headBellyShutdownTimer !== null) {
					clearTimeout(this.headBellyShutdownTimer);
					this.headBellyShutdownTimer = null;
				}
				if (!this.headActive && !this.bellyActive)
					this.headBellyHoldCooldown = false;
			} else if (!this.headBellyHoldCooldown) {
				this.headBellyHoldCooldown = true;
				this.headBellyHoldTimer = setTimeout(() => {
					this.headBellyHoldTimer = null;
					console.log(msg.nervous_system.eyes_full_reinit_trigger);
					this.eyes.sendCommand("restart_both", {});
					this.eyes.playAnimation("nervous_look", { replace: true });
				}, this.HEAD_BELLY_HOLD_MS);
				this.headBellyShutdownTimer = setTimeout(() => {
					this.headBellyShutdownTimer = null;
					console.log(msg.nervous_system.halt_trigger);
					const child = spawn("sudo", ["shutdown", "--halt", "now"], {
						detached: true,
						stdio: "ignore",
					});
					child.unref();
				}, this.HEAD_BELLY_SHUTDOWN_HOLD_MS);
			}
		}

		if (!active) return;

		// --- DEBOUNCE FILTER ---
		// We only reach this point on a touch DOWN event.
		// Check if the current time is too close to the last trigger.
		const now = Date.now();
		if (now - this.lastTouchTimes[sensor] < this.TOUCH_COOLDOWN_MS) {
			return; // Drop the event, it's electrical noise
		}
		// Register the valid touch time
		this.lastTouchTimes[sensor] = now;
		// -----------------------

		if (sensor === "head") {
			console.log(msg.nervous_system.head_touch);
			this.eyes.blink();
			this.eyes.playAnimation("nervous_look", { replace: true });
			console.log(msg.audio.purr_playing);
			playWav("pet.wav", 3.5);
		} else if (sensor === "belly") {
			this.handleBellyTouch();
		} else if (sensor === "shiver") {
			console.log(
				substitute(msg.nervous_system.shiver, { bcm: String(VIBE_BCM) }),
			);
			this.eyes.impulse();
		}
	}

	private onMotion(detected: boolean): void {
		if (detected) {
			if (!this.motionFirstDetectedLogged) {
				if (this.warmupComplete) {
					this.motionFirstDetectedLogged = true;
					console.log(msg.nervous_system.motion_sensor_triggered);
				} else {
					this.motionFirstDetectedPendingLog = true;
				}
			}
			if (this.motionClearDebounceTimer !== null) {
				clearTimeout(this.motionClearDebounceTimer);
				this.motionClearDebounceTimer = null;
			}
			if (this.motionSleepTimer !== null) {
				clearTimeout(this.motionSleepTimer);
				this.motionSleepTimer = null;
			}
			if (this.motionWasAsleep) {
				this.motionWasAsleep = false;
				console.log(msg.nervous_system.motion_detected);
				this.eyes.openEyes();
				setTimeout(
					() => this.eyes.playAnimation("nervous_look", { replace: true }),
					this.cfg.openThenLookMs,
				);
			}
		} else {
			if (this.motionClearDebounceTimer !== null)
				clearTimeout(this.motionClearDebounceTimer);
			this.motionClearDebounceTimer = setTimeout(() => {
				this.motionClearDebounceTimer = null;
				if (this.motionSleepTimer !== null) clearTimeout(this.motionSleepTimer);
				if (!this.warmupComplete) return;
				this.motionSleepTimer = setTimeout(() => {
					this.motionSleepTimer = null;
					this.motionWasAsleep = true;
					this.eyes.sleepClose(this.cfg.sleepCloseDurationS);
					console.log(msg.nervous_system.motion_sleep);
				}, this.cfg.motionSleepMs);
			}, this.cfg.motionClearDebounceMs);
		}
	}
}
