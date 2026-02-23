"""
CPython compat for MicroPython machine.SPI and machine.Pin.
Used by russhughes/gc9a01py on Raspberry Pi (spidev + RPi.GPIO).
"""

from __future__ import annotations

from typing import Any

try:
    import spidev
except ImportError:
    spidev = None  # type: ignore[assignment]

try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None  # type: ignore[assignment]


class SPI:
    """Thin wrapper so gc9a01py sees .write(buf). Uses spidev on Raspberry Pi."""

    def __init__(self, bus: int, device: int, baudrate: int = 10_000_000) -> None:
        """baudrate default 10 MHz; display.py passes SPI_BAUDRATE (env, default 60 MHz)."""
        if spidev is None:
            raise RuntimeError("spidev required; install with: pip install spidev (or apt install python3-spidev)")
        _spi_raw: Any = spidev.SpiDev()
        _spi_raw.open(bus, device)
        _spi_raw.mode = 0
        _spi_raw.max_speed_hz = baudrate
        self._spi: Any = _spi_raw

    # Linux SPI message size limit (e.g. 4096); chunk large writes
    _CHUNK_SIZE = 4096

    def write(self, buf: bytes | bytearray | object) -> None:
        """Write bytes to SPI (gc9a01py calls this). Chunks to avoid kernel limit."""
        if isinstance(buf, (bytearray, bytes)):
            data = buf
        else:
            data = bytes(buf)  # pyright: ignore[reportArgumentType]
        n = len(data)
        for i in range(0, n, self._CHUNK_SIZE):
            chunk = data[i : i + self._CHUNK_SIZE]
            self._spi.writebytes(list(chunk))

    def close(self) -> None:
        self._spi.close()


class Pin:
    """Thin wrapper so gc9a01py sees .on(), .off(), .value(). Uses RPi.GPIO (BCM)."""

    OUT = 1
    IN = 0

    def __init__(self, pin_id: int, mode: int = OUT) -> None:
        if GPIO is None:
            raise RuntimeError("RPi.GPIO required; install with: apt install python3-rpi.gpio")
        self._pin = pin_id
        self._mode = mode
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self._pin, GPIO.OUT if mode == self.OUT else GPIO.IN)

    def on(self):
        assert GPIO is not None  # already raised in __init__ if missing
        GPIO.output(self._pin, GPIO.HIGH)

    def off(self):
        assert GPIO is not None
        GPIO.output(self._pin, GPIO.LOW)

    def value(self, v: bool | int | None = None) -> int | None:
        assert GPIO is not None
        if v is None:
            return int(GPIO.input(self._pin))
        GPIO.output(self._pin, GPIO.HIGH if v else GPIO.LOW)
        return None
