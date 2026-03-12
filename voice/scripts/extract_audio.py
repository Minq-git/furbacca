import struct
import os

def extract_audio(rom_path, output_dir="audio"):
    """
    Extracts non-image entries (audio blocks) from rom_dump.bin.
    
    Logic:
    - First 4 bytes: Total entry count (N).
    - Next (N+1) * 4 bytes: Offset table.
    - Entry extraction: size = next_offset - current_offset.
    - If size != 256 (standard image size), it is extracted as audio.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    try:
        with open(rom_path, "rb") as f:
            # 1. Read the total count of entries
            count_data = f.read(4)
            if not count_data:
                print("Error: Could not read count from ROM.")
                return
            count = struct.unpack("<I", count_data)[0]
            print(f"Found {count} total entries in ROM.")

            # 2. Read the offset table
            offsets = []
            for i in range(count + 1):
                offset_data = f.read(4)
                if not offset_data:
                    break
                offsets.append(struct.unpack("<I", offset_data)[0])

            # 3. Iterate and extract
            extracted_count = 0
            for i in range(len(offsets) - 1):
                start = offsets[i]
                end = offsets[i+1]

                if start == 0 or end == 0:
                    continue

                size = end - start

                # Exclude standard 256-byte image blocks
                if size != 256:
                    f.seek(start)
                    data = f.read(size)
                    
                    filename = f"entry_{i}.bin"
                    output_path = os.path.join(output_dir, filename)
                    with open(output_path, "wb") as out:
                        out.write(data)
                    extracted_count += 1

            print(f"Extraction complete. Saved {extracted_count} files to '{output_dir}/'.")
            
    except FileNotFoundError:
        print(f"Error: {rom_path} not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    extract_audio("rom_dump.bin")
