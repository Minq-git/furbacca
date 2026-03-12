import struct

def inspect_rom(file_path):
    with open(file_path, "rb") as f:
        # Read the count of entries
        count_data = f.read(4)
        if not count_data:
            return
        count = struct.unpack("<I", count_data)[0]
        print(f"Total entries: {count}")

        # Read offsets (count + 1)
        offsets = []
        for i in range(count + 1):
            offset_data = f.read(4)
            if not offset_data:
                break
            offset = struct.unpack("<I", offset_data)[0]
            offsets.append(offset)

        # Inspect sizes between offsets
        for i in range(len(offsets) - 1):
            start = offsets[i]
            end = offsets[i+1]
            if start == 0 or end == 0:
                continue
            size = end - start
            if size > 256:
                print(f"Entry {i}: Offset {hex(start)}, Size {size} bytes")
            elif size < 0:
                 print(f"Entry {i}: Offset {hex(start)}, Negative Size {size} bytes (End {hex(end)})")

if __name__ == "__main__":
    inspect_rom("rom_dump.bin")
