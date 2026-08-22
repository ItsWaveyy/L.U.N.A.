import io

import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from kokoro import KPipeline


app = FastAPI(title="L.U.N.A. Kokoro TTS")

VOICE = "af_heart"
SAMPLE_RATE = 24000

pipeline = KPipeline(lang_code="a")


class SpeechRequest(BaseModel):
    text: str
    voice: str = VOICE


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "voice": VOICE,
        "sample_rate": SAMPLE_RATE,
    }


@app.post("/speak")
async def speak(request: SpeechRequest):
    text = request.text.strip()

    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    voice = request.voice or VOICE

    def generate_audio():
        generator = pipeline(text, voice=voice)

        for _, _, audio in generator:
            audio = np.asarray(audio)

            buffer = io.BytesIO()
            sf.write(
                buffer,
                audio,
                SAMPLE_RATE,
                format="WAV",
            )

            yield buffer.getvalue()

    return StreamingResponse(
        generate_audio(),
        media_type="audio/wav",
        headers={
            "X-Luna-TTS-Voice": voice,
            "X-Luna-TTS-Sample-Rate": str(SAMPLE_RATE),
        },
    )