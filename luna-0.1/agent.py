import asyncio
import io
import wave
from typing import AsyncIterable

import requests
from dotenv import load_dotenv

from livekit import agents, rtc
from livekit.agents import (
    AgentServer,
    AgentSession,
    Agent,
    room_io,
    function_tool,
    RunContext,
)
from livekit.agents.llm import StopResponse
from livekit.plugins import ai_coustics, google, groq

from core.orchestrator import LunaCore, SessionSleepWakeController
from prompts import AGENT_INSTRUCTION, build_session_instruction
from tools.memory import initialize_database, remember, recall


KOKORO_URL = "http://127.0.0.1:8880"
KOKORO_VOICE = "af_heart"


@function_tool()
async def get_weather(context: RunContext, city: str) -> str:
    from tools.weather import get_weather as _get_weather
    return await _get_weather(context, city)


@function_tool()
async def get_weather_forecast(
    context: RunContext,
    city: str,
    days: int = 3,
) -> str:
    from tools.weather import get_weather as _get_weather
    return await _get_weather(context, city, days=days)


@function_tool()
async def send_email(
    context: RunContext,
    recipient: str,
    subject: str,
    body: str,
) -> str:
    from tools.email import send_email as _send_email
    return await _send_email(context, recipient, subject, body)


@function_tool()
async def delegate_task(
    prompt: str,
    task: str = "general",
) -> str:
    from tools.delegate import delegate_task as _delegate_task
    return await _delegate_task(prompt=prompt, task=task)


load_dotenv()
initialize_database()


def synthesize_kokoro(text: str) -> bytes:
    """Send text to the local Kokoro service and return WAV bytes."""

    response = requests.post(
        f"{KOKORO_URL}/speak",
        json={
            "text": text,
            "voice": KOKORO_VOICE,
        },
        timeout=60,
    )

    response.raise_for_status()
    return response.content


def wav_to_audio_frames(wav_bytes: bytes):
    """Convert Kokoro WAV audio into LiveKit AudioFrames."""

    with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
        sample_rate = wav.getframerate()
        num_channels = wav.getnchannels()
        sample_width = wav.getsampwidth()

        if sample_width != 2:
            raise ValueError(
                f"Expected 16-bit PCM, got {sample_width * 8}-bit audio."
            )

        pcm_data = wav.readframes(wav.getnframes())

    samples_per_frame = int(sample_rate * 0.02)
    bytes_per_sample = num_channels * 2
    bytes_per_frame = samples_per_frame * bytes_per_sample

    for start in range(0, len(pcm_data), bytes_per_frame):
        chunk = pcm_data[start:start + bytes_per_frame]

        if not chunk:
            continue

        samples = len(chunk) // bytes_per_sample

        yield rtc.AudioFrame(
            data=chunk,
            sample_rate=sample_rate,
            num_channels=num_channels,
            samples_per_channel=samples,
        )


class Assistant(Agent):
    def __init__(
        self,
        sleep_controller: SessionSleepWakeController,
    ) -> None:
        self.sleep_controller = sleep_controller

        super().__init__(
            instructions=AGENT_INSTRUCTION,
            tools=[
                get_weather,
                get_weather_forecast,
                send_email,
                remember,
                recall,
                delegate_task,
            ],
        )

    async def on_user_turn_completed(
        self,
        turn_ctx,
        new_message,
    ) -> None:
        transcript = getattr(new_message, "text_content", None)

        if callable(transcript):
            transcript = transcript()

        if transcript is None:
            transcript = getattr(
                new_message,
                "raw_text_content",
                "",
            )

        self.sleep_controller.handle_transcript(transcript)

        if not self.sleep_controller.luna_core.listening:
            raise StopResponse()

    async def tts_node(
        self,
        text: AsyncIterable[str],
        model_settings,
    ) -> AsyncIterable[rtc.AudioFrame]:
        """Convert Gemini text into L.U.N.A.'s Kokoro voice."""

        text_parts = []

        async for chunk in text:
            text_parts.append(chunk)

        full_text = "".join(text_parts).strip()

        if not full_text:
            return

        wav_bytes = await asyncio.to_thread(
            synthesize_kokoro,
            full_text,
        )

        for frame in wav_to_audio_frames(wav_bytes):
            yield frame


server = AgentServer()


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: agents.JobContext):
    session = AgentSession(
        stt=groq.STT(),
        llm=google.LLM(
            model="gemini-3-flash-preview",
        ),
    )

    luna_core = LunaCore([])

    sleep_controller = SessionSleepWakeController(
        session,
        luna_core,
    )

    await session.start(
        room=ctx.room,
        agent=Assistant(sleep_controller),
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=ai_coustics.audio_enhancement(
                    model=ai_coustics.EnhancerModel.QUAIL_VF_S,
                ),
            ),
        ),
    )

    session.on(
        "user_input_transcribed",
        sleep_controller.handle_transcription_event,
    )

    await session.generate_reply(
        instructions=build_session_instruction(),
    )


if __name__ == "__main__":
    agents.cli.run_app(server)