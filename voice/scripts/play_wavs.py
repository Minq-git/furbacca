import os
import sys
import subprocess

def play_audio_files(directory):
    if not os.path.isdir(directory):
        print(f"Error: Directory '{directory}' does not exist.")
        return

    # Filter and sort .wav files
    files = [f for f in os.listdir(directory) if f.lower().endswith('.wav')]
    files.sort()

    if not files:
        print(f"No .wav files found in '{directory}'.")
        return

    print(f"Found {len(files)} files. Starting playback...")
    print("Press 'q' or 'ESC' in the ffplay window to skip to the next file.")
    print("Press Ctrl+C in this terminal to stop the script.")

    try:
        for filename in files:
            file_path = os.path.join(directory, filename)
            print(f"\n[Playing] {filename}")
            
            # -nodisp: disables graphical display
            # -autoexit: exits ffplay when the file finishes
            # -loglevel error: hides unnecessary logs
            cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", file_path]
            
            subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nPlayback stopped by user.")

if __name__ == "__main__":
    # Default to current directory if no argument is provided
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    play_audio_files(target_dir)
