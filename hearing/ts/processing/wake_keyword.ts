import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const SCRIPT_NAME = "check_wake.py";
const VENV_PYTHON = path.join(process.cwd(), "env", "bin", "python3");

const VOSK_MODEL_DEFAULT =
	process.env.VOSK_MODEL ?? "voice/models/vosk-model-small-en-us-0.15";

/**
 * Run the Python wake-word script (Vosk) on a PCM buffer (one-shot: spawns process per chunk).
 * Prefer createWakeDetector() so the model is loaded once.
 */
export function detectWakeWord(pcm: Buffer): Promise<boolean> {
	return new Promise((resolve) => {
		const scriptPath = path.join(process.cwd(), "hearing", "py", SCRIPT_NAME);
		const pyCmd = fs.existsSync(VENV_PYTHON) ? VENV_PYTHON : "python3";
		const py = spawn(pyCmd, [scriptPath], {
			cwd: process.cwd(),
			stdio: ["pipe", "pipe", "pipe"],
			env: { ...process.env, VOSK_MODEL: VOSK_MODEL_DEFAULT },
		});
		let out = "";
		py.stdout?.on("data", (c: Buffer) => {
			out += c.toString("utf8");
		});
		py.stderr?.on("data", (c: Buffer) => {
			process.stderr.write(c);
		});
		py.on("error", () => resolve(false));
		py.on("exit", () => {
			resolve(out.trim() === "WAKE");
		});
		py.stdin?.end(pcm);
	});
}

/**
 * Long-running wake-word detector: one Python process, model loaded once. Use this in the cortex
 * so we don't reload Vosk every chunk (which caused "he doesn't hear me" and LOG spam).
 */
export function createWakeDetector(): {
	checkChunk(pcm: Buffer): Promise<boolean>;
	close(): void;
} {
	const scriptPath = path.join(process.cwd(), "hearing", "py", SCRIPT_NAME);
	const pyCmd = fs.existsSync(VENV_PYTHON) ? VENV_PYTHON : "python3";
	let proc: ReturnType<typeof spawn> | null = null;
	let stdoutBuffer = "";
	let pendingResolve: ((woke: boolean) => void) | null = null;

	function spawnProcess(): void {
		if (proc) return;
		proc = spawn(pyCmd, [scriptPath, "--daemon"], {
			cwd: process.cwd(),
			stdio: ["pipe", "pipe", "pipe"],
			env: { ...process.env, VOSK_MODEL: VOSK_MODEL_DEFAULT },
		});
		proc.stderr?.on("data", (c: Buffer) => process.stderr.write(c));
		proc.stdout?.on("data", (c: Buffer) => {
			stdoutBuffer += c.toString("utf8");
			const lines = stdoutBuffer.split("\n");
			stdoutBuffer = lines.pop() ?? "";
			for (const line of lines) {
				const resolve = pendingResolve;
				pendingResolve = null;
				resolve?.(line.trim() === "WAKE");
			}
		});
		proc.on("error", () => {
			const resolve = pendingResolve;
			pendingResolve = null;
			proc = null;
			resolve?.(false);
		});
		proc.on("exit", () => {
			const resolve = pendingResolve;
			pendingResolve = null;
			proc = null;
			resolve?.(false);
		});
	}

	function close(): void {
		if (proc) {
			proc.kill("SIGTERM");
			proc = null;
		}
		const resolve = pendingResolve;
		pendingResolve = null;
		resolve?.(false);
	}

	function checkChunk(pcm: Buffer): Promise<boolean> {
		return new Promise((resolve) => {
			spawnProcess();
			if (!proc?.stdin?.writable) {
				resolve(false);
				return;
			}
			pendingResolve = resolve;
			const len = Buffer.allocUnsafe(4);
			len.writeUInt32LE(pcm.length, 0);
			const stdin = proc.stdin;
			if (stdin) {
				stdin.write(len, () => {});
				stdin.write(pcm, () => {});
			} else {
				pendingResolve = null;
				resolve(false);
			}
		});
	}

	return { checkChunk, close };
}
