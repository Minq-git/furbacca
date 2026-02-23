import fs from "node:fs";
import path from "node:path";

import { msg } from "../../../messages.js";
import type { TouchSenses } from "../../../senses/touch";
import type { EyeBridge } from "../../../vision/ts/eye_bridge.js";

// Same as Matter Lobe: repo .matter so fabric/CASE and pairing cache persist in one place
const MATTER_DIR = path.join(process.cwd(), ".matter");
const PAIRING_DISPLAY_CACHE = path.join(MATTER_DIR, "pairing_display.txt");
const PAIRING_QR_PATTERN =
	/Commissioning|passcode|discriminator|pairing|uncommissioned|qrcode|QR code|manual pairing|▄|▀|█|project-chip\.github\.io/i;

/** Result when Matter is enabled: buffer + whether we already printed pairing block and sep. */
export type MatterStartResult = {
	buffer: string[];
	showedCachedPairing: boolean;
};

export async function startMatterIfEnabled(opts: {
	enabled: boolean;
	eyes: EyeBridge;
	touch: TouchSenses;
	sep: string;
}): Promise<
	| (MatterStartResult & {
			matter: {
				notifyTouch(sensor: string, active: boolean): void;
				close(): Promise<void>;
			};
	  })
	| undefined
> {
	const { enabled, eyes, touch, sep } = opts;
	if (!enabled) {
		console.log(msg.nervous_system.matter_disabled);
		return undefined;
	}

	let showedCachedPairing = false;
	if (fs.existsSync(PAIRING_DISPLAY_CACHE)) {
		try {
			const cached = fs.readFileSync(PAIRING_DISPLAY_CACHE, "utf-8").trim();
			if (cached) {
				console.log(msg.nervous_system.matter_startup_logs_header);
				console.log(cached);
				console.log(sep);
				showedCachedPairing = true;
			}
		} catch {
			/* ignore read errors */
		}
	}

	const matterLogBuffer: string[] = [];
	// Use require() for local module so TS (node16/CJS) resolves without needing a sibling .js file in source.
	// eslint-disable-next-line @typescript-eslint/no-require-imports
	const { MatterLobe } =
		require("./matter_lobe") as typeof import("./matter_lobe.js");
	const matter = new MatterLobe(eyes, touch);

	try {
		await matter.start({
			onStatus: () => {},
			matterLogBuffer,
			pairingAlreadyShown: showedCachedPairing,
		});
	} catch (e) {
		console.error(e);
	}

	// Remove pairing block from subsequent prints if we already showed it from cache.
	if (showedCachedPairing) {
		for (let i = matterLogBuffer.length - 1; i >= 0; i--) {
			const line = matterLogBuffer[i];
			if (line !== undefined && PAIRING_QR_PATTERN.test(line))
				matterLogBuffer.splice(i, 1);
		}
	} else {
		const pairingLines = matterLogBuffer.filter((line) =>
			PAIRING_QR_PATTERN.test(line),
		);
		if (pairingLines.length > 0) {
			try {
				fs.mkdirSync(MATTER_DIR, { recursive: true });
				fs.writeFileSync(
					PAIRING_DISPLAY_CACHE,
					pairingLines.join("\n"),
					"utf-8",
				);
			} catch {
				/* ignore write errors */
			}
		}
	}

	// Expose the Matter instance to the caller (touch forwarding + shutdown close)
	return { buffer: matterLogBuffer, showedCachedPairing, matter };
}
