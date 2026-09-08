import io
from pathlib import Path

import requests


KOKORO_URL = "http://127.0.0.1:8880"
DEFAULT_VOICE = "af_heart"


def synthesize_speech(
    text: str,
    voice: str = DEFAULT_VOICE,
) -> bytes:
    """Generate speech through the local Kokoro service."""

    text = text.strip()

    if not text:
        raise ValueError("Text cannot be empty.")

    response = requests.post(
        f"{KOKORO_URL}/speak",
        json={
            "text": text,
            "voice": voice,
        },
        timeout=60,
    )

    response.raise_for_status()

    return response.content


def save_speech(
    text: str,
    output_path: str | Path,
    voice: str = DEFAULT_VOICE,
) -> Path:
    """Generate speech and save the returned WAV."""

    audio = synthesize_speech(text, voice=voice)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(audio)

    return output_path