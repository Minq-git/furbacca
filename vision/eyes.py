import board
import busio
import digitalio
import socket
import json
import time
from adafruit_rgb_display import st7789

# --- 1. SPI Hardware Setup ---
spi = busio.SPI(board.SCK, board.MOSI)

# Shared Pins
tft_dc = digitalio.DigitalInOut(board.D25)      # Pin 22
tft_res = digitalio.DigitalInOut(board.D27)     # Pin 13

# Unique CS Pins
cs_left = digitalio.DigitalInOut(board.D8)      # Pin 24
cs_right = digitalio.DigitalInOut(board.D7)     # Pin 26

# --- 2. Initialize Displays ---
# We use the ST7789 driver as a base, but we'll feed it the GC9A01 circular specs
left_eye = st7789.ST7789(
    spi, cs=cs_left, dc=tft_dc, rst=tft_res, 
    width=240, height=240, baudrate=64000000 # 64MHz for smooth eyes
)
right_eye = st7789.ST7789(
    spi, cs=cs_right, dc=tft_dc, rst=tft_res, 
    width=240, height=240, baudrate=64000000
)

# --- 3. UDP Bridge Setup ---
UDP_IP = "127.0.0.1"
UDP_PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
sock.setblocking(False)

def clear_screens():
    # Fill with a specific color to test the wiring
    # 0xF800 is Red in RGB565 format
    left_eye.fill(0xF800)
    right_eye.fill(0x001F) # Blue
    print("Screens cleared: Left (Red), Right (Blue)")

def run_eyes():
    print("Furbacca Vision Online. Waiting for Nervous System commands...")
    clear_screens()
    
    while True:
        try:
            data, _ = sock.recvfrom(1024)
            msg = json.loads(data.decode())
            
            if msg['action'] == 'blink':
                left_eye.fill(0x0000) # Black
                right_eye.fill(0x0000)
                time.sleep(0.1)
                clear_screens() # Back to colors
                
        except BlockingIOError:
            pass
        
        time.sleep(0.01)

if __name__ == "__main__":
    run_eyes()