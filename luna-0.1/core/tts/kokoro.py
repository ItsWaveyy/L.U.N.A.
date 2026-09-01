import asyncio
import io
import time
import wave
from typing import AsyncIterator
from core.timing import luna_log

import requests

from livekit import rtc
from livekit.agents import tts, APIConnectOptions


KOKORO_URL = "http://127.0.0.1:8880"
KOKORO_VOICE = "af_heart"


def synthesize_kokoro(text: str, voice: str) -> bytes:
    """Send text to the local Kokoro service and return WAV bytes."""

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


def wav_to_audio_frames(
    wav_bytes: bytes,
):
    """Convert a Kokoro WAV file into LiveKit AudioFrames."""

    with wave.open(
        io.BytesIO(wav_bytes),
        "rb",
    ) as wav:
        sample_rate = wav.getframerate()
        num_channels = wav.getnchannels()
        sample_width = wav.getsampwidth()

        if sample_width != 2:
            raise ValueError(
                f"Expected 16-bit PCM, "
                f"got {sample_width * 8}-bit audio."
            )

        pcm_data = wav.readframes(
            wav.getnframes()
        )

    samples_per_frame = int(
        sample_rate * 0.02
    )

    bytes_per_sample = num_channels * 2

    bytes_per_frame = (
        samples_per_frame
        * bytes_per_sample
    )

    for start in range(
        0,
        len(pcm_data),
        bytes_per_frame,
    ):
        chunk = pcm_data[
            start:start + bytes_per_frame
        ]

        if not chunk:
            continue

        samples = (
            len(chunk)
            // bytes_per_sample
        )

        yield rtc.AudioFrame(
            data=chunk,
            sample_rate=sample_rate,
            num_channels=num_channels,
            samples_per_channel=samples,
        )


class KokoroTTS(tts.TTS):
    """
    LiveKit TTS adapter for the local Kokoro service.

    LiveKit handles the AgentSession/TTS lifecycle.
    Kokoro handles the actual speech synthesis.
    """

    def __init__(
        self,
        url: str = KOKORO_URL,
        voice: str = KOKORO_VOICE,
    ) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(
                streaming=False,
            ),
            sample_rate=24000,
            num_channels=1,
        )

        self.url = url.rstrip("/")
        self.voice = voice

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = APIConnectOptions(),
        **kwargs,
    ) -> tts.ChunkedStream:

        return KokoroChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
        )


class KokoroChunkedStream(tts.ChunkedStream):
    """Non-streaming LiveKit TTS stream backed by Kokoro."""

    def __init__(
        self,
        *,
        tts: KokoroTTS,
        input_text: str,
        conn_options: APIConnectOptions,
    ) -> None:
        super().__init__(
            tts=tts,
            input_text=input_text,
            conn_options=conn_options,
        )

        self._kokoro = tts

    async def _run(
        self,
        output_emitter: tts.AudioEmitter,
    ) -> None:
        started = time.perf_counter()

        wav_bytes = await asyncio.to_thread(
            synthesize_kokoro,
            self.input_text,
            self._kokoro.voice,
        )

        synthesis_time = (
            time.perf_counter()
            - started
        )

        frames = list(
            wav_to_audio_frames(
                wav_bytes
            )
        )

        audio_duration = sum(
            frame.samples_per_channel
            / frame.sample_rate
            for frame in frames
        )

        print(
            "[L.U.N.A.] Kokoro timing: "
            f"synthesis={synthesis_time:.3f}s "
            f"audio={audio_duration:.3f}s "
            f"rtf={(
                synthesis_time / audio_duration
                if audio_duration > 0
                else 0.0
            ): .2f}x"
        )

        output_emitter.initialize(
            request_id="kokoro",
            sample_rate=self._kokoro.sample_rate,
            num_channels=self._kokoro.num_channels,
            mime_type="audio/pcm",
            stream=False,
        )

        for frame in frames:
            output_emitter.push(
                frame.data.tobytes()
            )

        output_emitter.flush()


class KokoroChunkedStream(tts.ChunkedStream):
    """Non-streaming LiveKit TTS stream backed by Kokoro."""

    def __init__(
        self,
        *,
        tts: KokoroTTS,
        input_text: str,
        conn_options: APIConnectOptions,
    ) -> None:
        super().__init__(
            tts=tts,
            input_text=input_text,
            conn_options=conn_options,
        )

        self._kokoro = tts

    async def _run(
        self,
        output_emitter: tts.AudioEmitter,
    ) -> None:
        started = time.perf_counter()

        wav_bytes = await asyncio.to_thread(
            synthesize_kokoro,
            self.input_text,
            self._kokoro.voice,
        )

        synthesis_time = (
            time.perf_counter()
            - started
        )

        frames = list(
            wav_to_audio_frames(wav_bytes)
        )

        audio_duration = sum(
            frame.samples_per_channel
            / frame.sample_rate
            for frame in frames
        )

        luna_log(
            "Kokoro timing: "
            f"synthesis={synthesis_time:.3f}s "
            f"audio={audio_duration:.3f}s "
            f"rtf={(
                synthesis_time / audio_duration
                if audio_duration > 0
                else 0.0
            ): .2f}x"
        )

        output_emitter.initialize(
            request_id="kokoro",
            sample_rate=self._kokoro.sample_rate,
            num_channels=self._kokoro.num_channels,
            mime_type="audio/pcm",
            stream=False,
        )

        for frame in frames:
            output_emitter.push(
                frame.data.tobytes()
            )

        output_emitter.flush()