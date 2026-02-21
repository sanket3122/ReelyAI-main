import os
import subprocess
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from config import ELEVENLABS_API_KEY

client = ElevenLabs(
    api_key=ELEVENLABS_API_KEY,
)

def text_to_speech_file(text: str, folder: str, voice_id: str) -> str:
    # Calling the text_to_speech conversion API with detailed parameters
    response = client.text_to_speech.convert(
        voice_id = voice_id,
        output_format="mp3_22050_32",
        text=text,
        model_id="eleven_turbo_v2_5",

        voice_settings=VoiceSettings(
            stability=0.0,
            similarity_boost=1.0,
            style=0.0,
            use_speaker_boost=True,
            speed=1.0,
        ),
    )

    # uncomment the line below to play the audio back
    # play(response)

    # Generating a unique file name for the output MP3 file
    save_file_path = os.path.join(f"user_uploads/{folder}", "audio.mp3")

    # Writing the audio to a file
    with open(save_file_path, "wb") as f:
        for chunk in response:
            if chunk:
                f.write(chunk)

    print(f"{save_file_path}: A new audio file was saved successfully!")

    # Return the path of the saved audio file
    return save_file_path


def generate_music(folder: str) -> str | None:
    """Generate background music from a text prompt using ElevenLabs Music API.
    Returns the saved file path, or None if no music prompt exists."""
    music_prompt_path = os.path.join(f"user_uploads/{folder}", "music.txt")

    if not os.path.exists(music_prompt_path):
        return None

    with open(music_prompt_path, "r", encoding="utf-8") as f:
        prompt = f.read().strip()

    if not prompt:
        return None

    print(f"Generating background music for {folder}: '{prompt}'")

    response = client.music.compose(
        prompt=prompt,
        music_length_ms=8000,
        output_format="mp3_44100_128",
    )

    raw_path = os.path.join(f"user_uploads/{folder}", "music_raw.mp3")
    save_file_path = os.path.join(f"user_uploads/{folder}", "music.mp3")

    with open(raw_path, "wb") as f:
        for chunk in response:
            if chunk:
                f.write(chunk)

    # Trim to 5 seconds to cut off the silent tail before looping
    subprocess.run([
        "ffmpeg", "-y", "-i", raw_path,
        "-t", "5", "-c", "copy", save_file_path
    ], check=True, capture_output=True)

    os.remove(raw_path)

    print(f"{save_file_path}: Background music saved successfully!")
    return save_file_path
