import "dotenv/config";
import { Reflexes } from "./brain/ts/cortex/reflexes.js";
import { VisualCortex } from "./brain/ts/cortex/visual_cortex.js";
import { startMatterIfEnabled } from "./brain/ts/matter/matter_boot.js";
import { MicStream } from "./hearing/ts/hardware/mic_stream.js";
import { AuditoryCortex } from "./hearing/ts/processing/auditory_cortex.js";
import { Brainstem } from "./homeostasis/brainstem.js";
import { msg, substitute } from "./messages.js";
import { TouchSenses } from "./senses/touch";
import { EyeBridge } from "./vision/ts/eye_bridge.js";

async function main(): Promise<void> {
	const eyes = new EyeBridge();
	const touch = new TouchSenses(0);

	const brainstem = new Brainstem(eyes);
	const cortex = new VisualCortex(eyes);
	const reflexes = new Reflexes(eyes, touch, brainstem.getReflexesConfig());

	const mic = new MicStream(process.env.FURBACCA_MIC_CARD ?? "0");
	const hearing = new AuditoryCortex(mic);
	hearing.setOnWake(() => {
		eyes.openEyes();
	});

	await brainstem.boot();
	console.log(msg.nervous_system.header);

	const visionHost = process.env.VISION_HOST ?? "127.0.0.1";
	const visionPort = process.env.VISION_PORT ?? "5005";
	console.log(
		substitute(msg.nervous_system.eyes_listening, {
			host: visionHost,
			port: visionPort,
		}),
	);
	console.log(
		substitute(msg.nervous_system.voice_ready, {
			card: process.env.FURBACCA_AUDIO_CARD ?? "0",
		}),
	);
	if (
		process.platform === "linux" &&
		(process.env.FURBACCA_EYE_TRACK ?? process.env.VISION_EYE_TRACK ?? "1") !==
			"0"
	) {
		console.log(msg.nervous_system.eye_tracker_starting);
	}

	await Promise.all([
		Promise.resolve(cortex.startListening()),
		Promise.resolve(hearing.startListening()),
	]);
	const { usingTouchEvents, usingMotionEvents } = reflexes.startListening();

	brainstem.advanceWarmup(1); // NS / Voice
	brainstem.advanceWarmup(2); // Touch arming
	brainstem.advanceWarmup(3); // Motion arming
	brainstem.advanceWarmup(4); // Status
	brainstem.advanceWarmup(5); // Matter starting

	if (usingTouchEvents) console.log(msg.nervous_system.touch_event_driven);
	else console.log(msg.nervous_system.touch_polling);
	if (usingMotionEvents) {
		console.log(msg.nervous_system.motion_event_driven);
		console.log(msg.nervous_system.motion_sensor_enabled);
	}

	const matterEnabled =
		process.env.FURBACCA_MATTER !== "0" &&
		process.env.FURBACCA_MATTER !== "false";
	if (matterEnabled) console.log(msg.nervous_system.matter_lobe_enabled);

	const sep = msg.nervous_system.hardware_table_sep;
	let matterForShutdown: { close(): Promise<void> } | null = null;
	const matterPromise = startMatterIfEnabled({
		enabled: matterEnabled,
		eyes,
		touch,
		sep,
	}).then((res) => {
		if (res?.matter) {
			matterForShutdown = res.matter;
			reflexes.setMatter(res.matter);
		}
		return res;
	});

	process.on("SIGINT", () => {
		void brainstem.shutdown(async () => {
			await matterForShutdown?.close();
			await Promise.all([
				reflexes.stopListening(),
				cortex.stopListening(),
				Promise.resolve(hearing.stopListening()),
			]);
		});
	});

	brainstem.startWarmupThenOpen(matterPromise, reflexes);
}

void main();
