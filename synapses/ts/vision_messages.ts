/**
 * UDP 5005: Nervous System → Eyes
 * All commands are JSON with an "action" field; main_eyes.py dispatches by action.
 */

export interface LookCommand {
	action: "look";
	x: number; // -1.0 to 1.0
	y: number; // -1.0 to 1.0
	pupil_mode?: "normal" | "wide" | "narrow";
}

export interface AnimationCommand {
	action: "animation";
	name: string; // e.g. "double_blink" | "nervous_look" | "shiver" | "sleep_close"
	replace?: boolean;
}

export interface EyesOpenCommand {
	action: "eyes_open";
}

export interface EyesCloseCommand {
	action: "eyes_close";
}

export interface SleepCloseCommand {
	action: "sleep_close";
	duration_s?: number;
}

export interface WarmupCommand {
	action: "warmup";
	step: number;
}

export interface SetEyeShapeCommand {
	action: "set_eye_shape";
	shape: string;
}

export interface SetEyeTypeCommand {
	action: "set_eye_type";
	type?: string;
	eye_type?: string;
}

export interface CycleEyeTypeCommand {
	action: "cycle_eye_type";
}

export interface BlinkCommand {
	action: "blink";
}

export interface ImpulseCommand {
	action: "impulse";
}

export interface RestartBothCommand {
	action: "restart_both";
}

export type EyesCommand =
	| LookCommand
	| AnimationCommand
	| EyesOpenCommand
	| EyesCloseCommand
	| SleepCloseCommand
	| WarmupCommand
	| SetEyeShapeCommand
	| SetEyeTypeCommand
	| CycleEyeTypeCommand
	| BlinkCommand
	| ImpulseCommand
	| RestartBothCommand;

/**
 * UDP 5006: Camera / eye-track → Nervous System
 */
export interface EyeTrackingEvent {
	event:
		| "eye_tracking_started"
		| "eye_tracking_stopped"
		| "looking_started"
		| "looking_stopped"
		| "looking_at";
	label?: string;
	confidence?: number;
	x?: number; // raw pixel or normalized
	y?: number;
}
