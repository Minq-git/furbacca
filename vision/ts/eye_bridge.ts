import * as dgram from 'dgram';

export class EyeBridge {
  private client = dgram.createSocket('udp4');
  private PORT = 5005;
  private HOST = process.env.VISION_HOST ?? '127.0.0.1'; // Use VISION_HOST when eyes run on another machine (e.g. Pi)

  public sendCommand(action: string, params: object = {}) {
    const message = Buffer.from(JSON.stringify({ action, ...params }));
    this.client.send(message, this.PORT, this.HOST, (err) => {
      if (err) console.error("Eye Bridge Error:", err.message);
    });
  }

  /** Play a named animation (e.g. 'nervous_look': eyes look left then right 2–3 times). */
  public playAnimation(name: string) {
    this.sendCommand('animation', { name });
  }

  /** Set eye shape at runtime (e.g. 'round', 'sharp', 'bean', 'oval', 'pill'). */
  public setEyeShape(shape: string) {
    this.sendCommand('set_eye_shape', { shape });
  }

  /** Cycle to the next eye shape. */
  public cycleEyeShape() {
    this.sendCommand('cycle_eye_shape');
  }
}