# CPython compat for micropython.const (gc9a01py uses "from micropython import const").

from typing import TypeVar

T = TypeVar("T")


def const(value: T) -> T:
    """MicroPython const(): identity for CPython (no constant folding)."""
    return value
