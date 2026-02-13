# CPython compat for MicroPython machine API (used by gc9a01py on Raspberry Pi).
from .machine import SPI, Pin

__all__ = ["SPI", "Pin"]
