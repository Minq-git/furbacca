import { Gpio } from 'onoff';

// Pin Mappings from instruction.md
const HEAD_TOUCH_PIN = 17; // GPIO 17 (Pin 11)
const BELLY_TOUCH_PIN = 22; // GPIO 22 (Pin 15)

// Initialize Sensors
const headSensor = new Gpio(HEAD_TOUCH_PIN, 'in', 'both', { debounceTimeout: 10 });
const bellySensor = new Gpio(BELLY_TOUCH_PIN, 'in', 'both', { debounceTimeout: 10 });

console.log("--- Furbacca Nervous System Online ---");
console.log(`Monitoring Head (GPIO ${HEAD_TOUCH_PIN}) and Belly (GPIO ${BELLY_TOUCH_PIN})...`);

// Head Touch Logic
headSensor.watch((err, value) => {
    if (err) {
        console.error("Head Sensor Error:", err);
        return;
    }
    if (value === 1) {
        console.log("🐾 Head Pet Detected! (Triggering Matter Event...)");
        // TODO: Insert Matter.js trigger here
    } else {
        console.log("🐾 Head Pet Released.");
    }
});

// Belly Touch Logic
bellySensor.watch((err, value) => {
    if (err) {
        console.error("Belly Sensor Error:", err);
        return;
    }
    if (value === 1) {
        console.log("Tickle Detected! (Triggering Animatronics...)");
    }
});

// Graceful Shutdown
process.on('SIGINT', () => {
    console.log("\nShutting down nervous system...");
    headSensor.unexport();
    bellySensor.unexport();
    process.exit();
});