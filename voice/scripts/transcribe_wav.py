import sys
import os
from google import genai

def get_clean_text(response):
    """Extracts only the text parts from the response, avoiding SDK warnings."""
    try:
        # Access parts directly to avoid the SDK's warning logger in response.text
        parts = response.candidates[0].content.parts
        return "".join([part.text for part in parts if part.text is not None])
    except (AttributeError, IndexError):
        return response.text if hasattr(response, 'text') else str(response)

def transcribe_audio(file_path):
    # Initialize the client
    # Ensure GEMINI_API_KEY is set in your environment variables
    client = genai.Client()

    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        return

    print(f"Uploading {file_path}...")
    # Upload the file to the Gemini API
    myfile = client.files.upload(file=file_path)

    print("Transcribing...")
    # Use the flash model for fast transcription
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=[
            "Please provide a high-quality transcription of this audio clip. "
            "Only return the transcript text, no extra commentary.",
            myfile
        ]
    )

    text = get_clean_text(response).strip()
    print("\n--- Transcript ---")
    print(text)
    print("------------------")

    # Save to .txt file
    txt_path = os.path.splitext(file_path)[0] + ".txt"
    try:
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Saved transcript to: {txt_path}")
    except Exception as e:
        print(f"Error saving transcript: {e}")

if __name__ == "__main__":
    # Use the first command line argument as the file path, 
    # or default to 'entry_0.wav' if available.
    default_file = "entry_0.wav"
    target_file = sys.argv[1] if len(sys.argv) > 1 else default_file

    if not os.path.exists(target_file) and target_file == default_file:
        print("Usage: python transcribe_wav.py <path_to_wav_file>")
    else:
        transcribe_audio(target_file)
