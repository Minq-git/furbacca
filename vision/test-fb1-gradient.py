#!/usr/bin/env python3
"""Write a test gradient to /dev/fb1 (gc9a01 overlay, 240x240 RGB565). Run: python3 vision/test-fb1-gradient.py"""
import struct

try:
    fb = open("/dev/fb1", "wb")
except PermissionError:
    print("Need sudo: sudo python3 vision/test-fb1-gradient.py")
    raise

for y in range(240):
    for x in range(240):
        r = x * 255 // 239
        g = y * 255 // 239
        b = 128
        c = (r & 0xF8) << 8 | (g & 0xFC) << 3 | (b >> 3)
        fb.write(struct.pack("<H", c))
fb.close()
print("Wrote gradient to /dev/fb1")
