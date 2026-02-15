/**
 * Declaration for @matter/types/clusters/identify so the import resolves
 * when the package's exports don't provide types (e.g. on some Node/tsc setups).
 */
declare module "@matter/types/clusters/identify" {
  export namespace Identify {
    export enum EffectIdentifier {
      Blink = 0,
      Breathe = 1,
      Okay = 2,
      ChannelChange = 11,
      FinishEffect = 254,
      StopEffect = 255,
    }
    export interface TriggerEffectRequest {
      effectIdentifier: EffectIdentifier;
      effectVariant?: number;
    }
  }
}
