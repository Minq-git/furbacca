import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const SCRIPT_NAME = "check_wake.py";
const VENV_PYTHON = path.join(process.cwd(), "env", "bin", "python3");

/**
 * Run the Python wake-word script (Vosk) on a PCM buffer. Returns true if "Hey Furbacca" (or "furbacca") was detected.
 * Requires: pip install vosk, and a Vosk model at VOSK_MODEL or voice/models/vosk-model-small-en-us-0.15.
 * Uses env/bin/python3 when present (venv from setup-fresh) so vosk is available.
 */
export function detectWakeWord(pcm: Buffer): Promise<boolean> {
	return new Promise((resolve) => {
		const scriptPath = path.join(process.cwd(), "hearing", "py", SCRIPT_NAME);
		const pyCmd = fs.existsSync(VENV_PYTHON) ? VENV_PYTHON : "python3";
		const py = spawn(pyCmd, [scriptPath], {
			cwd: process.cwd(),
			stdio: ["pipe", "pipe", "pipe"],
			env: {
				...process.env,
				VOSK_MODEL:
					process.env.VOSK_MODEL ?? "voice/models/vosk-model-small-en-us-0.15",
			},
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
