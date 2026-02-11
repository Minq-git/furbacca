"""
CPython compat for MicroPython machine.SPI and machine.Pin.
Used by russhughes/gc9a01py on Raspberry Pi (spidev + RPi.GPIO).
"""
import time

try:
    import spidev
except ImportError:
    spidev = None

try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None


class SPI:
    """Thin wrapper so gc9a01py sees .write(buf). Uses spidev on Raspberry Pi."""

    def __init__(self, bus, device, baudrate=10_000_000):
        """baudrate default 10 MHz; display.py passes SPI_BAUDRATE (env, default 60 MHz)."""
        if spidev is None:
            raise RuntimeError("spidev required; install with: pip install spidev (or apt install python3-spidev)")
        self._spi = spidev.SpiDev()
        self._spi.open(bus, device)
        self._spi.mode = 0
        self._spi.max_speed_hz = baudrate

    # Linux SPI message size limit (e.g. 4096); chunk large writes
    _CHUNK_SIZE = 4096

    def write(self, buf):
        """Write bytes to SPI (gc9a01py calls this). Chunks to avoid kernel limit."""
        if isinstance(buf, (bytearray, bytes)):
            data = buf
        else:
            data = bytes(buf)
        n = len(data)
        for i in range(0, n, self._CHUNK_SIZE):
            chunk = data[i : i + self._CHUNK_SIZE]
            self._spi.writebytes(list(chunk))

    def close(self):
        self._spi.close()


class Pin:
    """Thin wrapper so gc9a01py sees .on(), .off(), .value(). Uses RPi.GPIO (BCM)."""

    OUT = 1
    IN = 0

    def __init__(self, pin_id, mode=OUT):
        if GPIO is None:
            raise RuntimeError("RPi.GPIO required; install with: apt install python3-rpi.gpio")
        self._pin = pin_id
        self._mode = mode
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self._pin, GPIO.OUT if mode == self.OUT else GPIO.IN)

    def on(self):
        GPIO.output(self._pin, GPIO.HIGH)

    def off(self):
        GPIO.output(self._pin, GPIO.LOW)

    def value(self, v=None):
        if v is None:
            return GPIO.input(self._pin)
        GPIO.output(self._pin, GPIO.HIGH if v else GPIO.LOW)
