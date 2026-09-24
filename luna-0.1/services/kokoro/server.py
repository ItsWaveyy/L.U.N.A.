import io
import time

import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from kokoro import KModel, KPipeline


app = FastAPI(title="L.U.N.A. Kokoro TTS")

VOICE = "af_heart"
SAMPLE_RATE = 24000

model = KModel(
    repo_id="hexgrad/Kokoro-82M",
).eval()

pipeline = KPipeline(
    lang_code="a",
    repo_id="hexgrad/Kokoro-82M",
    model=model,
)

pipeline.load_single_voice(VOICE)

generator = model.decoder.generator


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
        raise HTTPException(
            status_code=400,
            detail="Text cannot be empty.",
        )

    voice = request.voice or VOICE

    audio_chunks = []

    generation_started = time.perf_counter()
    generator_created = time.perf_counter()
    generator = pipeline(text, voice=voice)
    generator_create_time = time.perf_counter() - generator_created

    first_chunk_time = None
    chunk_count = 0
    for _, _, audio in generator:
        if first_chunk_time is None:
            first_chunk_time = time.perf_counter() - generation_started

        chunk_count += 1
        audio = np.asarray(audio, dtype=np.float32)
        audio_chunks.append(audio)

    generation_time = time.perf_counter() - generation_started

    print(
        f"[KOKORO] generator creation: {generator_create_time:.3f}s "
        f"total generation: {generation_time:.3f}s"
    )

    print(
        f"[KOKORO] raw generation: {generation_time:.3f}s "
        f"first_chunk={first_chunk_time:.3f}s "
        f"chunks={chunk_count}"
    )

    if not audio_chunks:
        raise HTTPException(
            status_code=500,
            detail="Kokoro generated no audio.",
        )

    audio = np.concatenate(audio_chunks)

    # Correct Kokoro's abnormally quiet onset.
    #
    # Kokoro produces a very low-level ramp at the beginning of some
    # outputs before reaching normal speech level. Boost only that
    # transition window; leave the established speech untouched.
    reference_start = int(0.29 * SAMPLE_RATE)
    correction_end = int(0.37 * SAMPLE_RATE)
    max_gain = 75.0
    smoothing_samples = int(0.02 * SAMPLE_RATE)

    if len(audio) > reference_start + smoothing_samples:
        reference = audio[reference_start:correction_end]

        reference_rms = float(np.sqrt(np.mean(reference ** 2)))

        if reference_rms > 0:
            for start in range(
                reference_start,
                min(correction_end, len(audio)),
                smoothing_samples,
            ):
                end = min(start + smoothing_samples, len(audio))
                window = audio[start:end]

                window_rms = float(np.sqrt(np.mean(window ** 2)))

                if window_rms > 0:
                    gain = min(
                        reference_rms / window_rms,
                        max_gain,
                    )

                    audio[start:end] *= gain

            print(
                f"[KOKORO] onset correction: "
                f"reference_rms={reference_rms:.6f} "
                f"window=290-370ms "
                f"max_gain={max_gain:.1f}x"
            )

    buffer = io.BytesIO()

    sf.write(
        buffer,
        audio,
        SAMPLE_RATE,
        format="WAV",
        subtype="PCM_16",
    )

    return Response(
        content=buffer.getvalue(),
        media_type="audio/wav",
        headers={
            "X-Luna-TTS-Voice": voice,
            "X-Luna-TTS-Sample-Rate": str(SAMPLE_RATE),
        },
    )