/**
 * Touch sensors (TTP223B) and SW-420 vibration.
 * Head: BCM 17. Belly: BCM 22. Vibration DO: BCM 23 (Logic 0 = detected).
 *
 * Two modes:
 * - Event-driven: startEventWatch() spawns gpiomon (libgpiod) for ~instant response.
 * - Polling fallback: poll() with setInterval when gpiomon is not available.
 */
import { type ChildProcess, execSync, spawn } from "node:child_process";
import { msg, substitute } from "../messages.js";

const VIBE_BCM = 23;

const OFFSET_HEAD = 17;
const OFFSET_BELLY = 22;
const OFFSET_VIBE = 23;
const EDGE_RISING = 1;
const EDGE_FALLING = 2;

export type TouchSensor = "head" | "belly" | "shiver";

export type TouchCallback = (sensor: TouchSensor, active: boolean) => void;

const TOUCH_DEBOUNCE_MS = 80;

export class TouchSenses {
	private chipNum: number;
	private lastVibe: number = 1;
	private gpiomonProcess: ChildProcess | null = null;
	// Debounce state for poll mode (head/belly only)
	private pollEmittedHead: boolean = false;
	private pollEmittedBelly: boolean = false;
	private pollTimerHead: ReturnType<typeof setTimeout> | null = null;
	private pollTimerBelly: ReturnType<typeof setTimeout> | null = null;

	constructor(chip: number) {
		this.chipNum = chip;
	}

	/** Check if gpiomon (libgpiod) is available for event-driven mode. */
	static hasGpiomon(): boolean {
		try {
			execSync("which gpiomon", { encoding: "utf-8" });
			return true;
		} catch {
			return false;
		}
	}

	/** Label width for hardware table rows (must match vision/py/display.py). */
	static readonly HARDWARE_LABEL_WIDTH = 34;

	/**
	 * Verify head touch GPIO (BCM 17) is readable. Only runs on Linux.
	 */
	static checkHeadTouch(chip: number): { ok: boolean; message: string } {
		if (process.platform !== "linux") {
			return { ok: true, message: "" };
		}
		try {
			execSync(`gpioget -c ${chip} --numeric ${OFFSET_HEAD}`, {
				encoding: "utf-8",
				stdio: ["ignore", "pipe", "pipe"],
			});
			return { ok: true, message: "" };
		} catch (e: unknown) {
			const err = e instanceof Error ? e.message : String(e);
			return {
				ok: false,
				message: substitute(msg.touch.head_touch_gpio_error, {
					error: err.trim().split("\n")[0] ?? err,
				}),
			};
		}
	}

	/**
	 * Verify belly touch GPIO (BCM 22) is readable. Only runs on Linux.
	 */
	static checkBellyTouch(chip: number): { ok: boolean; message: string } {
		if (process.platform !== "linux") {
			return { ok: true, message: "" };
		}
		try {
			execSync(`gpioget -c ${chip} --numeric ${OFFSET_BELLY}`, {
				encoding: "utf-8",
				stdio: ["ignore", "pipe", "pipe"],
			});
			return { ok: true, message: "" };
		} catch (e: unknown) {
			const err = e instanceof Error ? e.message : String(e);
			return {
				ok: false,
				message: substitute(msg.touch.belly_touch_gpio_error, {
					error: err.trim().split("\n")[0] ?? err,
				}),
			};
		}
	}

	/**
	 * Verify vibration GPIO line (BCM 23) is readable. Only runs on Linux.
	 */
	static checkVibration(chip: number): { ok: boolean; message: string } {
		if (process.platform !== "linux") {
			return { ok: true, message: "" };
		}
		try {
			execSync(`gpioget -c ${chip} --numeric ${OFFSET_VIBE}`, {
				encoding: "utf-8",
				stdio: ["ignore", "pipe", "pipe"],
			});
			return { ok: true, message: "" };
		} catch (e: unknown) {
			const err = e instanceof Error ? e.message : String(e);
			return {
				ok: false,
				message: substitute(msg.touch.vibration_gpio_error, {
					error: err.trim().split("\n")[0] ?? err,
				}),
			};
		}
	}

	/**
	 * Start event-driven watch using gpiomon. Head and belly are debounced (only report after line stable 80ms) to avoid TTP223B bounce/noise spam.
	 * Returns a stop function that returns a Promise resolved when gpiomon has exited (so GPIO is released). If gpiomon is not available, returns null (use poll() instead).
	 */
	startEventWatch(callback: TouchCallback): (() => Promise<void>) | null {
		if (!TouchSenses.hasGpiomon()) {
			return null;
		}
		const timers: Partial<Record<"head" | "belly", ReturnType<typeof setTimeout>>> = {};
		const debounced: TouchCallback = (sensor, active) => {
			if (sensor === "shiver") {
				callback(sensor, active);
				return;
			}
			const key = sensor;
			const t = timers[key];
			if (t) {
				clearTimeout(t);
				timers[key] = undefined;
			}
			timers[key] = setTimeout(() => {
				timers[key] = undefined;
				callback(sensor, active);
			}, TOUCH_DEBOUNCE_MS);
		};
		const proc = spawn(
			"gpiomon",
			[
				"-c",
				String(this.chipNum),
				"-F",
				"%o %e\n",
				"-e",
				"both",
				String(OFFSET_HEAD),
				String(OFFSET_BELLY),
				String(OFFSET_VIBE),
			],
			{ stdio: ["ignore", "pipe", "pipe"] },
		);
		this.gpiomonProcess = proc;
		let buffer = "";
		proc.stdout?.on("data", (chunk: Buffer) => {
			buffer += chunk.toString();
			const lines = buffer.split("\n");
			buffer = lines.pop() ?? "";
			for (const line of lines) {
				const parts = line.trim().split(/\s+/);
				if (parts.length >= 2) {
					const offset = parseInt(parts[0], 10);
					const edge = parseInt(parts[1], 10);
					const sensor = this.offsetToSensor(offset);
					if (sensor) {
						const active = this.edgeToActive(sensor, edge);
						debounced(sensor, active);
					}
				}
			}
		});
		proc.stderr?.on("data", (d) => process.stderr.write(d));
		proc.on("error", () => {
			this.gpiomonProcess = null;
		});
		proc.on("exit", () => {
			this.gpiomonProcess = null;
		});
		return () => {
			if (timers.head) clearTimeout(timers.head);
			if (timers.belly) clearTimeout(timers.belly);
			timers.head = timers.belly = undefined;
			const p = this.gpiomonProcess;
			this.gpiomonProcess = null;
			if (!p) return Promise.resolve();
			return new Promise<void>((resolve) => {
				const done = () => {
					clearTimeout(t);
					resolve();
				};
				p.once("exit", done);
				p.kill("SIGTERM");
				const t = setTimeout(() => {
					p.removeListener("exit", done);
					try {
						p.kill("SIGKILL");
					} catch {
						/* already gone */
					}
					resolve();
				}, 2000);
			});
		};
	}

	private offsetToSensor(offset: number): TouchSensor | null {
		if (offset === OFFSET_HEAD) return "head";
		if (offset === OFFSET_BELLY) return "belly";
		if (offset === OFFSET_VIBE) return "shiver";
		return null;
	}

	/** Vibration sensor: Logic 0 = detected, so falling edge = active. Head/Belly: rising = touch. */
	private edgeToActive(sensor: TouchSensor, edge: number): boolean {
		if (sensor === "shiver") return edge === EDGE_FALLING;
		return edge === EDGE_RISING;
	}

	private readPins(): [number, number, number] {
		try {
			const out = execSync(`gpioget -c ${this.chipNum} --numeric 17 22 23`, {
				encoding: "utf-8",
			});
			const parts = out.trim().split(/\s+/);
			return [
				parseInt(parts[0], 10),
				parseInt(parts[1], 10),
				parseInt(parts[2], 10),
			];
		} catch {
			return [0, 0, 1];
		}
	}

	/** Polling mode: call each tick to detect changes. Head and belly debounced (80ms) like event watch. Use when gpiomon is not available. */
	public poll(callback: TouchCallback): void {
		const [head, belly, vibe] = this.readPins();
		const headActive = !!head;
		const bellyActive = !!belly;
		if (headActive !== this.pollEmittedHead) {
			if (this.pollTimerHead) clearTimeout(this.pollTimerHead);
			const value = headActive;
			this.pollTimerHead = setTimeout(() => {
				this.pollTimerHead = null;
				this.pollEmittedHead = value;
				callback("head", value);
			}, TOUCH_DEBOUNCE_MS);
		}
		if (bellyActive !== this.pollEmittedBelly) {
			if (this.pollTimerBelly) clearTimeout(this.pollTimerBelly);
			const value = bellyActive;
			this.pollTimerBelly = setTimeout(() => {
				this.pollTimerBelly = null;
				this.pollEmittedBelly = value;
				callback("belly", value);
			}, TOUCH_DEBOUNCE_MS);
		}
		if (vibe !== this.lastVibe) {
			this.lastVibe = vibe;
			if (vibe === 0) callback("shiver", true);
		}
	}
}

export { VIBE_BCM };
