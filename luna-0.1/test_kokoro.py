from kokoro import KPipeline
import soundfile as sf
import numpy as np
import time

TEXT = """
Good evening, sir. LUNA is online and ready to assist.
I have access to your memory, local systems, and several external AI services.
How may I help you?
"""

VOICES = [
    "af_heart",
    "af_bella",
    "af_sarah",
    "af_sky",
    "af_nicole",
]

pipeline = KPipeline(lang_code="a")

for voice in VOICES:
    print(f"\nGenerating {voice}...")

    start = time.perf_counter()

    generator = pipeline(TEXT, voice=voice)

    chunks = []
    for _, _, audio in generator:
        chunks.append(audio)

    audio = np.concatenate(chunks)

    elapsed = time.perf_counter() - start

    filename = f"kokoro_{voice}.wav"
    sf.write(filename, audio, 24000)

    duration = len(audio) / 24000
    realtime_factor = elapsed / duration

    print(f"Saved: {filename}")
    print(f"Generation time: {elapsed:.2f}s")
    print(f"Audio duration: {duration:.2f}s")
    print(f"Realtime factor: {realtime_factor:.2f}x")
