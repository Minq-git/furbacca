import { execSync, spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import type { Reflexes } from "../brain/ts/reflexes.js";
import { msg } from "../messages.js";
import { TouchSenses } from "../senses/touch";
import type { EyeBridge } from "../vision/ts/eye_bridge.js";
import { fanControl } from "./fan_control.js";

export type WarmupConfig = {
	EYE_WARMUP_STEPS: number;
	WARMUP_MS: number;
	WARMUP_BEIGE: [number, number, number];
	WARMUP_GREEN: [number, number, number];
	STATUS_FAIL_RED: [number, number, number];
	OPEN_THEN_LOOK_MS: number;
	MOTION_SLEEP_MS: number;
	MOTION_CLEAR_DEBOUNCE_MS: number;
	SLEEP_CLOSE_DURATION_S: number;
};

type MatterStartResult =
	| { buffer: string[]; showedCachedPairing: boolean }
	| undefined;

const ANSI_RESET = "\x1b[0m";
const CLEAR_LINE = "\x1b[0K";

function ansiRgb(r: number, g: number, b: number): string {
	return `\x1b[38;2;${r};${g};${b}m`;
}

function loadWarmupConfig(): WarmupConfig {
	const repoRoot = process.cwd();
	const scriptPath = path.join(
		repoRoot,
		"vision",
		"py",
		"export_warmup_config.py",
	);
	const out = execSync(`python3 "${scriptPath}"`, {
		encoding: "utf-8",
		cwd: repoRoot,
	});
	return JSON.parse(out) as WarmupConfig;
}

function readDisplayStatus(): "ok" | "fail" | "unknown" {
	const filePath = path.join(process.cwd(), ".furbacca-hardware.json");
	for (let i = 0; i < 2; i++) {
		try {
			if (fs.existsSync(filePath)) {
				const data = JSON.parse(fs.readFileSync(filePath, "utf-8")) as {
					displays?: string;
				};
				return data.displays === "ok"
					? "ok"
					: data.displays === "fail"
						? "fail"
						: "unknown";
			}
		} catch {
			/* ignore */
		}
		if (i === 0 && process.platform === "linux") {
			try {
				execSync("sleep 1.5", { stdio: "ignore" });
			} catch {
				break;
			}
		}
	}
	return "unknown";
}

type StatusState = "unknown" | "ok" | "fail";

export class Brainstem {
	private eyes: EyeBridge;
	private cfg: WarmupConfig;

	private readonly WARMUP_STEP_LABELS: string[];
	private warmupSteps: number;

	// Eyes subprocess
	private eyesChild: ReturnType<typeof spawn> | null = null;
	private isShuttingDown = false;
	private readonly EYES_RESTART_DELAY_MS = 2000;

	/** Buffer eyes output until warmup bar is done so logs don't interleave with the progress line. */
	private eyesOutputBuffer: string[] = [];
	private eyesOutputBuffered = true;

	constructor(eyes: EyeBridge) {
		this.eyes = eyes;
		this.cfg = loadWarmupConfig();
		this.warmupSteps = this.cfg.EYE_WARMUP_STEPS;
		this.WARMUP_STEP_LABELS = [
			"Hardware ready",
			"NS / Voice",
			"Touch arming",
			"Motion arming",
			"Status",
			"Matter starting",
			"Preparing eyes…",
			"Ready",
		];

		// First: prevent fan from floating (BCM 24 LOW) before any other GPIO or heavy work
		fanControl.init();
	}

	public getReflexesConfig(): {
		openThenLookMs: number;
		motionSleepMs: number;
		motionClearDebounceMs: number;
		sleepCloseDurationS: number;
	} {
		return {
			openThenLookMs: this.cfg.OPEN_THEN_LOOK_MS,
			motionSleepMs: this.cfg.MOTION_SLEEP_MS,
			motionClearDebounceMs: this.cfg.MOTION_CLEAR_DEBOUNCE_MS,
			sleepCloseDurationS: this.cfg.SLEEP_CLOSE_DURATION_S,
		};
	}

	private statusCell(state: StatusState): string {
		const [r, g, b] =
			state === "ok"
				? this.cfg.WARMUP_GREEN
				: state === "fail"
					? this.cfg.STATUS_FAIL_RED
					: this.cfg.WARMUP_BEIGE;
		const char = state === "unknown" ? "--" : state === "ok" ? "✓" : "✕";
		const padLeft = state === "unknown" ? "   " : "   ";
		const padRight = state === "unknown" ? "   " : "   ";
		return padLeft + ansiRgb(r, g, b) + char + ANSI_RESET + padRight;
	}

	private warmupSegmentColor(blend: number): [number, number, number] {
		return [
			Math.round(
				this.cfg.WARMUP_BEIGE[0] * (1 - blend) +
					this.cfg.WARMUP_GREEN[0] * blend,
			),
			Math.round(
				this.cfg.WARMUP_BEIGE[1] * (1 - blend) +
					this.cfg.WARMUP_GREEN[1] * blend,
			),
			Math.round(
				this.cfg.WARMUP_BEIGE[2] * (1 - blend) +
					this.cfg.WARMUP_GREEN[2] * blend,
			),
		];
	}

	private warmupBar(filled: number, total: number, label: string): string {
		const pct = total > 0 ? Math.round((filled / total) * 100) : 0;
		let bar = "[";
		for (let i = 0; i < total; i++) {
			if (i < filled) {
				const blend = total > 1 ? i / (total - 1) : 0;
				const [r, g, b] = this.warmupSegmentColor(blend);
				bar += `${ansiRgb(r, g, b)}█${ANSI_RESET}`;
			} else {
				bar += "░";
			}
		}
		bar += "]";
		return `  ${bar} (${pct}%): ${label}`;
	}

	public advanceWarmup(step: number): void {
		const label = this.WARMUP_STEP_LABELS[step] ?? "Starting";
		if (step === 0) {
			process.stdout.write(`${this.warmupBar(0, this.warmupSteps, label)}\n`);
		} else {
			process.stdout.write(
				`\r${CLEAR_LINE}${this.warmupBar(step, this.warmupSteps, label)}`,
			);
		}
		this.eyes.warmup(step);
	}

	private forwardWithPrefix(
		stream: NodeJS.ReadableStream,
		prefix: string,
	): void {
		stream.setEncoding("utf8");
		stream.on("data", (chunk: string) => {
			const lines = String(chunk).split(/\r?\n/).filter(Boolean);
			for (const line of lines) {
				const out = `${prefix + line}\n`;
				if (this.eyesOutputBuffered) this.eyesOutputBuffer.push(out);
				else process.stderr.write(out);
			}
		});
	}

	private flushEyesBuffer(): void {
		this.eyesOutputBuffered = false;
		for (const line of this.eyesOutputBuffer) process.stderr.write(line);
		this.eyesOutputBuffer.length = 0;
	}

	private startEyesProcess(): void {
		const repoRoot = process.cwd();
		const scriptPath = path.join(repoRoot, "vision", "py", "main_eyes.py");
		const venvPython = path.join(repoRoot, "env", "bin", "python3");
		const pythonPath = fs.existsSync(venvPython) ? venvPython : "python3";
		this.eyesChild = spawn(pythonPath, [scriptPath], {
			cwd: repoRoot,
			env: { ...process.env, PYTHONUNBUFFERED: "1", UDP_BIND: "0.0.0.0" },
			stdio: ["ignore", "pipe", "pipe"],
		});
		if (this.eyesChild.stdout)
			this.forwardWithPrefix(this.eyesChild.stdout, "");
		if (this.eyesChild.stderr)
			this.forwardWithPrefix(this.eyesChild.stderr, "");
		this.eyesChild.on("exit", () => {
			this.eyesChild = null;
			if (this.isShuttingDown) return;
			console.log(msg.nervous_system.eyes_restarted);
			setTimeout(() => this.startEyesProcess(), this.EYES_RESTART_DELAY_MS);
		});
	}

	public async boot(): Promise<void> {
		// Start eyes first so they bind while we print the table; spinner shows on displays as early as possible
		this.startEyesProcess();

		const displayStatus = readDisplayStatus();
		const headHw = TouchSenses.checkHeadTouch(0);
		const bellyHw = TouchSenses.checkBellyTouch(0);
		const vibeHw = TouchSenses.checkVibration(0);
		const sep = msg.nervous_system.hardware_table_sep;
		const header = msg.nervous_system.hardware_table_header;

		const displayState = (): StatusState =>
			displayStatus === "unknown"
				? "unknown"
				: displayStatus === "ok"
					? "ok"
					: "fail";
		const headState = (): StatusState =>
			process.platform !== "linux" ? "unknown" : headHw.ok ? "ok" : "fail";
		const bellyState = (): StatusState =>
			process.platform !== "linux" ? "unknown" : bellyHw.ok ? "ok" : "fail";
		const vibeState = (): StatusState =>
			process.platform !== "linux" ? "unknown" : vibeHw.ok ? "ok" : "fail";
		const fanState = (): StatusState => {
			if (
				process.env.FURBACCA_FAN === "0" ||
				process.env.FURBACCA_FAN === "false"
			)
				return "unknown";
			if (process.platform !== "linux") return "unknown";
			return fanControl.isInitialized() ? "ok" : "fail";
		};
		const voiceState = (): StatusState => {
			if (process.platform !== "linux") return "unknown";
			try {
				execSync("which aplay", { stdio: "ignore" });
				return "ok";
			} catch {
				return "fail";
			}
		};

		const rows: string[] = [
			"| GC9A01PY    | Left Eye            | 8        | " +
				this.statusCell(displayState()) +
				" |",
			"| GC9A01PY    | Right Eye           | 7        | " +
				this.statusCell(displayState()) +
				" |",
			"| TTP223B     | Head Touch          | 17       | " +
				this.statusCell(headState()) +
				" |",
			"| TTP223B     | Belly Touch         | 22       | " +
				this.statusCell(bellyState()) +
				" |",
			"| SW-420      | Vibration (Shiver)  | 23       | " +
				this.statusCell(vibeState()) +
				" |",
			"| MAX98357A   | Voice (I2S)         | 18,19,21 | " +
				this.statusCell(voiceState()) +
				" |",
			"| Cooling     | Fan (BCM 24)        | 24       | " +
				this.statusCell(fanState()) +
				" |",
		];

		console.log(msg.nervous_system.hardware_table_title);
		console.log(sep);
		console.log(header);
		console.log(sep);
		for (const row of rows) {
			console.log(row);
		}
		console.log(sep);

		if (process.platform === "linux") {
			try {
				execSync("sleep 1.2", { stdio: "ignore" });
			} catch {
				/* ignore */
			}
		}

		this.advanceWarmup(0);

		// Fan ramp after startup begins (safe even if no-op on non-Linux)
		void fanControl.softStart().then(() => fanControl.startThermalWatchdog());
	}

	public startWarmupThenOpen(
		matterResultPromise: Promise<MatterStartResult>,
		reflexes: Reflexes,
	): void {
		this.advanceWarmup(6);
		this.advanceWarmup(7);
		this.flushEyesBuffer();
		process.stdout.write(
			"\r" +
				CLEAR_LINE +
				this.warmupBar(this.warmupSteps, this.warmupSteps, "Opening eyes.") +
				"\n",
		);
		reflexes.markWarmupComplete();

		this.eyes.openEyes();
		matterResultPromise.then((result) => {
			if (result?.buffer?.length) {
				console.log(msg.nervous_system.matter_startup_logs_header);
				result.buffer.forEach((line) => {
					console.log(line);
				});
			}
			if (!result?.showedCachedPairing)
				console.log(msg.nervous_system.hardware_table_sep);
			this.eyes.openEyes();
			setTimeout(
				() => this.eyes.playAnimation("nervous_look", { replace: true }),
				800,
			);
		});
	}

	public async shutdown(cleanup: () => Promise<void>): Promise<void> {
		if (this.isShuttingDown) return;
		this.isShuttingDown = true;

		if (this.eyesChild) {
			this.eyesChild.kill("SIGTERM");
			this.eyesChild = null;
		}
		this.eyes.closeEyes();
		await cleanup();
		process.exit(0);
	}
}
