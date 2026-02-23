/**
 * Custom IdentifyServer that implements triggerEffect and maps Matter identify effects
 * to Furbacca eye animations.
 *
 * Eyes are provided via the node environment: set EyeBridgeForIdentify before adding the eye endpoint.
 *
 * Use createFurbaccaExtendedColorLight() with device/requirements from the same module that runs node.add()
 * so the custom Identify server shares the SDK's Behavior prototype chain (fixes "is not a Behavior.Type" on Pi).
 */
import { Identify } from "@matter/types/clusters/identify";
import type { EyeBridge } from "../../vision/ts/eye_bridge.js";

/** Environment key: set node.env.set(EyeBridgeForIdentify, eyes) before adding the eye endpoint. */
export class EyeBridgeForIdentify {
	static readonly id = "EyeBridgeForIdentify";
}

/** Build the custom device using the same ExtendedColorLight types passed in (from matter_lobe's import of @matter/node/devices). */
export function createFurbaccaExtendedColorLight(
	ExtendedColorLightDeviceDefinition: {
		with: (...behaviors: unknown[]) => unknown;
	},
	ExtendedColorLightRequirements: {
		IdentifyServer: new (...args: unknown[]) => { endpoint: unknown };
	},
): unknown {
	const BaseIdentifyWithTrigger = ExtendedColorLightRequirements.IdentifyServer;

	class FurbaccaIdentifyServer extends BaseIdentifyWithTrigger {
		triggerEffect(request: Identify.TriggerEffectRequest): void {
			const endpoint = (
				this as unknown as {
					endpoint: { env: { maybeGet: (k: unknown) => unknown } };
				}
			).endpoint;
			const eyes = endpoint.env.maybeGet(EyeBridgeForIdentify) as
				| EyeBridge
				| undefined;
			if (!eyes) return;

			switch (request.effectIdentifier) {
				case Identify.EffectIdentifier.Blink:
					eyes.blink();
					break;
				case Identify.EffectIdentifier.Breathe:
					eyes.playAnimation("nervous_look", { replace: true });
					break;
				case Identify.EffectIdentifier.Okay:
					eyes.blink();
					eyes.playAnimation("double_blink", { replace: true });
					break;
				case Identify.EffectIdentifier.ChannelChange:
					eyes.impulse();
					break;
				case Identify.EffectIdentifier.FinishEffect:
				case Identify.EffectIdentifier.StopEffect:
					break;
				default:
					eyes.blink();
			}
		}
	}

	return ExtendedColorLightDeviceDefinition.with(FurbaccaIdentifyServer);
}
