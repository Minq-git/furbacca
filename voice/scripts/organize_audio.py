import os
import shutil
import json
import re
from google import genai

# Initialize Client
# Ensure GEMINI_API_KEY is set in your environment variables
client = genai.Client()

def get_clean_text(response):
    """Extracts only the text parts from the response."""
    try:
        parts = response.candidates[0].content.parts
        return "".join([part.text for part in parts if part.text is not None])
    except (AttributeError, IndexError):
        return response.text if hasattr(response, 'text') else str(response)

def analyze_and_organize(file_path):
    print(f"\n[Processing] {file_path}")
    
    try:
        # Upload file to the Gemini API
        myfile = client.files.upload(file=file_path)
        
        # Determine sound type, suggest category, name, and transcription
        prompt = (
            "Analyze this audio clip. Identify what sounds are being made (e.g., speech, animal, mechanical, ambient). "
            "Suggest a category name for a folder (one word, lowercase), "
            "a short, descriptive filename (lowercase, underscores, no extension), "
            "and provide a high-quality transcription or description of the sound. "
            "Return ONLY a JSON object: {\"category\": \"...\", \"filename\": \"...\", \"transcription\": \"...\"}"
        )
        
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[prompt, myfile]
        )
        
        # Clean the JSON response
        text = get_clean_text(response).strip()
        # Remove potential markdown code blocks
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
            
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            print(f"  [Error] Failed to parse JSON from response: {text}")
            return

        category = data.get("category", "other").lower().replace(" ", "_")
        suggested_name = data.get("filename", os.path.basename(file_path)).lower().replace(" ", "_")
        transcription = data.get("transcription", "").strip()
        
        # Ensure name doesn't have multiple extensions
        if suggested_name.endswith(".wav"):
            suggested_name = suggested_name[:-4]
            
        # Create destination directory
        dest_dir = os.path.join(os.getcwd(), category)
        os.makedirs(dest_dir, exist_ok=True)
        
        # Check for filename collisions
        dest_base_name = suggested_name
        dest_wav_path = os.path.join(dest_dir, f"{dest_base_name}.wav")
        
        counter = 1
        while os.path.exists(dest_wav_path):
            dest_base_name = f"{suggested_name}_{counter}"
            dest_wav_path = os.path.join(dest_dir, f"{dest_base_name}.wav")
            counter += 1
            
        # Move and rename the wav file
        shutil.move(file_path, dest_wav_path)
        
        # Save the transcription to a .txt file
        dest_txt_path = os.path.join(dest_dir, f"{dest_base_name}.txt")
        with open(dest_txt_path, "w", encoding="utf-8") as f:
            f.write(transcription)
            
        print(f"  [Success] Categorized as '{category}' and renamed to '{dest_base_name}.wav'")
        print(f"  [Success] Saved transcript to '{dest_base_name}.txt'")
        
    except Exception as e:
        print(f"  [Error] Failed to process {file_path}: {e}")

def main():
    # List all .wav files in current directory
    files = [f for f in os.listdir('.') if f.lower().endswith('.wav')]
    # Sort files to process them consistently
    files.sort()
    
    print(f"Found {len(files)} files to process.")
    
    # Iterate and organize
    for f in files:
        analyze_and_organize(f)

if __name__ == "__main__":
    main()
