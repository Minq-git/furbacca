import { spawn } from "node:child_process";
import path from "node:path";

import { msg, substitute } from "../../messages.js";
import { monitorMotion } from "../../senses/motion.js";
import {
	type TouchCallback,
	type TouchSenses,
	type TouchSensor,
	VIBE_BCM,
} from "../../senses/touch";
import type { EyeBridge } from "../../vision/ts/eye_bridge.js";

// Optional: load at runtime so Pi can start even if dist/voice/ts/audio.js wasn't built (e.g. voice/ts not synced)
let initAudio: () => void = () => {};
let playPurr: () => void = () => {};
let playGiggle: () => void = () => {};
try {
	// eslint-disable-next-line @typescript-eslint/no-require-imports
	const audio = require("../../voice/ts/audio.js");
	initAudio = audio.initAudio;
	playPurr = audio.playPurr;
	playGiggle = audio.playGiggle;
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

	/** Head + belly: 5s = eyes re-init, 30s = network heal script (long to avoid accidental trigger). */
	private readonly HEAD_BELLY_HOLD_MS = 5000;
	private readonly NETWORK_HEAL_HOLD_MS = 30000;
	private headBellyHoldTimer: ReturnType<typeof setTimeout> | null = null;
	private networkHealTimer: ReturnType<typeof setTimeout> | null = null;
	private headBellyHoldCooldown = false;

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
		if (this.networkHealTimer !== null) {
			clearTimeout(this.networkHealTimer);
			this.networkHealTimer = null;
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
		playGiggle();
		this.eyes.cycleEyeType();
		this.eyes.sendCommand("look", { x: 0, y: 0, pupil_mode: "wide" });
		this.chipToolOn();
	}

	private onTouch(sensor: TouchSensor, active: boolean): void {
		if (sensor === "head") this.headActive = active;
		else if (sensor === "belly") this.bellyActive = active;

		this.matter?.notifyTouch(sensor, active);

		// Head + belly: 5s → eyes re-init; 30s → network heal script
		if (sensor === "head" || sensor === "belly") {
			if (!this.headActive || !this.bellyActive) {
				if (this.headBellyHoldTimer !== null) {
					clearTimeout(this.headBellyHoldTimer);
					this.headBellyHoldTimer = null;
				}
				if (this.networkHealTimer !== null) {
					clearTimeout(this.networkHealTimer);
					this.networkHealTimer = null;
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
				this.networkHealTimer = setTimeout(() => {
					this.networkHealTimer = null;
					console.log(msg.nervous_system.network_heal_trigger);
					this.eyes.sendCommand("set_eye_type", { type: "demon" });
					const scriptPath = path.join(
						process.cwd(),
						"scripts",
						"diagnostics",
						"heal-network.sh",
					);
					const child = spawn("bash", [scriptPath], {
						detached: true,
						stdio: "ignore",
					});
					child.unref();
				}, this.NETWORK_HEAL_HOLD_MS);
			}
		}

		if (!active) return;
		if (sensor === "head") {
			console.log(msg.nervous_system.head_touch);
			this.eyes.blink();
			this.eyes.playAnimation("nervous_look", { replace: true });
			console.log(msg.audio.purr_playing);
			playPurr();
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
