import { TouchSenses } from './senses/touch';
import { EyeBridge } from './vision/eye_bridge';

const touch = new TouchSenses(0); // or 4
const eyes = new EyeBridge();

console.log("--- Furbacca Nervous System: Modular Edition ---");

setInterval(() => {
  touch.poll((sensor, active) => {
    if (active) {
      console.log(`🐾 ${sensor} trigger detected!`);
      
      // Route the signal to the eyes
      if (sensor === 'head') {
        eyes.sendCommand('blink');
        eyes.sendCommand('look', { x: 120, y: 40 });
      }
    }
  });
}, 20);