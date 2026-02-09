# CPython compat for micropython.const (gc9a01py uses "from micropython import const").

def const(value):
    """MicroPython const(): identity for CPython (no constant folding)."""
    return value
