#!/usr/bin/env node
/**
 * Test fan on BCM 24: init, soft-start to 100%, hold 5s, then off.
 * Run from repo root on the Pi (after build):
 *   npm run build:pi && node dist/scripts/test-fan.js
 * (Use build:pi on Pi to avoid tsc OOM; if already built, just: node dist/scripts/test-fan.js)
 *
 * Force fan on for this run (ignore FURBACCA_FAN=0):
 *   FURBACCA_FAN=1 node dist/scripts/test-fan.js
 */
if (process.env.FURBACCA_FAN !== "1" && process.env.FURBACCA_FAN !== "true") {
	process.env.FURBACCA_FAN = "1";
}

const RUN_SEC = 5;

async function main(): Promise<void> {
	const { fanControl } = await import("../cooling/fan_control.js");
	fanControl.init();
	if (!fanControl.isInitialized()) {
		console.error("Fan did not initialize. Check:");
		console.error("  - Running on Linux with gpiod: gpiod libgpiod-dev");
		console.error(
			"  - GPIO access: sudo usermod -aG gpio $USER (then log out/in) or run with sudo",
		);
		console.error(
			"  - BCM 24 (physical pin 18) wiring: 1kΩ → 2N2222 base, fan 5V→collector, emitter GND",
		);
		process.exit(1);
	}
	console.log(
		"Fan init OK. Soft-start 0→100% over 2s, then 100% for",
		RUN_SEC,
		"s...",
	);
	await fanControl.softStart(2000);
	fanControl.setSpeed(100);
	await new Promise((r) => setTimeout(r, RUN_SEC * 1000));
	fanControl.setSpeed(0);
	console.log("Fan off. Test done.");
	process.exit(0);
}

main().catch((e) => {
	console.error(e);
	process.exit(1);
});
