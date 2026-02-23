"""
CPython compat for MicroPython machine.SPI and machine.Pin.
Used by russhughes/gc9a01py on Raspberry Pi (spidev + RPi.GPIO).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, cast

try:
    import spidev  # pyright: ignore[reportMissingImports]
except ImportError:
    spidev = None  # type: ignore[assignment]

try:
    import RPi.GPIO as GPIO  # pyright: ignore[reportMissingModuleSource]
except ImportError:
    GPIO = None  # type: ignore[assignment]


class _SpiDevLike(Protocol):
    mode: int
    max_speed_hz: int

    def open(self, bus: int, device: int) -> None: ...
    def writebytes(self, values: Sequence[int]) -> None: ...
    def close(self) -> None: ...


class _GpioLike(Protocol):
    BCM: int
    OUT: int
    IN: int
    HIGH: int
    LOW: int

    def setmode(self, mode: int) -> None: ...
    def setwarnings(self, state: bool) -> None: ...
    def setup(self, channel: int, mode: int) -> None: ...
    def output(self, channel: int, value: int) -> None: ...
    def input(self, channel: int) -> int: ...


class SPI:
    """Thin wrapper so gc9a01py sees .write(buf). Uses spidev on Raspberry Pi."""

    def __init__(self, bus: int, device: int, baudrate: int = 10_000_000) -> None:
        """baudrate default 10 MHz; display.py passes SPI_BAUDRATE (env, default 60 MHz)."""
        if spidev is None:
            raise RuntimeError("spidev required; install with: pip install spidev (or apt install python3-spidev)")
        spi_ctor = getattr(spidev, "SpiDev", None)
        if spi_ctor is None:
            raise RuntimeError("spidev module missing SpiDev()")
        _spi_raw = cast(_SpiDevLike, spi_ctor())
        _spi_raw.open(bus, device)
        _spi_raw.mode = 0
        _spi_raw.max_speed_hz = baudrate
        self._spi: _SpiDevLike = _spi_raw

    # Linux SPI message size limit (e.g. 4096); chunk large writes
    _CHUNK_SIZE: int = 4096

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
        gpio = cast(_GpioLike, GPIO)
        self._pin = pin_id
        self._mode = mode
        gpio.setmode(gpio.BCM)
        gpio.setwarnings(False)
        gpio.setup(self._pin, gpio.OUT if mode == self.OUT else gpio.IN)

    def on(self) -> None:
        assert GPIO is not None  # already raised in __init__ if missing
        gpio = cast(_GpioLike, GPIO)
        gpio.output(self._pin, gpio.HIGH)

    def off(self) -> None:
        assert GPIO is not None
        gpio = cast(_GpioLike, GPIO)
        gpio.output(self._pin, gpio.LOW)

    def value(self, v: bool | int | None = None) -> int | None:
        assert GPIO is not None
        gpio = cast(_GpioLike, GPIO)
        if v is None:
            return int(gpio.input(self._pin))
        gpio.output(self._pin, gpio.HIGH if v else gpio.LOW)
        return None
