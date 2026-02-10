#ifndef _CONFIG_H_
#define _CONFIG_H_

// --- DISPLAY SETTINGS ---
#define WIDTH  240
#define HEIGHT 240

// --- FURBACCA GC9A01 PINOUT (BCM / GPIO) ---
// Single source of truth for vision/eyes.py pinout.
// Physical pin numbers (40-pin header) per instruction.md:
//
//   Signal      GPIO  Physical   Linux SPI device
//   --------    ----  --------   -----------------
//   SCLK        11    23         SPI0 SCLK (shared)
//   MOSI        10    19         SPI0 MOSI (shared)
//   DC          25    22         Data/Command
//   RST (RES)   27    13         Reset
//   CS Left      8    24         /dev/spidev0.0 (Left Eye)
//   CS Right     7    26         /dev/spidev0.1 (Right Eye)
//
#define DISPLAY_DC     25  // GPIO 25, Physical 22
#define DISPLAY_RESET  27  // GPIO 27, Physical 13
#define DISPLAY_CS_L    8  // GPIO 8,  Physical 24 → spidev0.0
#define DISPLAY_CS_R    7  // GPIO 7,  Physical 26 → spidev0.1

// --- GC9A01 SPECIFIC TWEAKS ---
#define BAUDRATE 64000000 
#define SPI_PORT 0
#define EYE_SHAPE_CIRCULAR // Masks the rendering for round screens

// --- EYE BEHAVIOR ---
#define TRACKING           // Eyelid follows the pupil
#define AUTOBLINK          // Eyes blink on their own randomly
#define SYMMETRICAL_EYELID // Good for Furbys to avoid looking "cross-eyed"

#endif