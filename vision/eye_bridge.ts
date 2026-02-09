import * as dgram from 'dgram';

export class EyeBridge {
  private client = dgram.createSocket('udp4');
  private PORT = 5005;
  private HOST = '127.0.0.1'; // Internal loopback address

  public sendCommand(action: string, params: object = {}) {
    const message = Buffer.from(JSON.stringify({ action, ...params }));
    
    this.client.send(message, this.PORT, this.HOST, (err) => {
      if (err) console.error("Eye Bridge Error:", err.message);
    });
  }
}