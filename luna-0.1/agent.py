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
    TurnHandlingOptions,
    EndpointingOptions,
    InterruptionOptions,
)
from livekit.agents.llm import StopResponse
from livekit.plugins import ai_coustics, google, groq
from livekit.plugins import silero

from core.orchestrator import LunaCore, SessionSleepWakeController
from core.standby.manager import StandbyManager
from core.identity.audio import SpeakerAudioBuffer
from core.identity.speaker import SpeakerIdentity

from prompts import AGENT_INSTRUCTION, build_session_instruction
from tools.memory import initialize_database, remember, recall


KOKORO_URL = "http://127.0.0.1:8880"
KOKORO_VOICE = "af_heart"


@function_tool()
async def get_weather(
    context: RunContext,
    city: str,
) -> str:
    from tools.weather import get_weather as _get_weather

    return await _get_weather(
        context,
        city,
    )


@function_tool()
async def get_weather_forecast(
    context: RunContext,
    city: str,
    days: int = 3,
) -> str:
    from tools.weather import get_weather as _get_weather

    return await _get_weather(
        context,
        city,
        days=days,
    )


@function_tool()
async def send_email(
    context: RunContext,
    recipient: str,
    subject: str,
    body: str,
) -> str:
    from tools.email import send_email as _send_email

    return await _send_email(
        context,
        recipient,
        subject,
        body,
    )


@function_tool()
async def delegate_task(
    prompt: str,
    task: str = "general",
) -> str:
    from tools.delegate import delegate_task as _delegate_task

    return await _delegate_task(
        prompt=prompt,
        task=task,
    )


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


def wav_to_audio_frames(
    wav_bytes: bytes,
):
    """Convert Kokoro WAV audio into LiveKit AudioFrames."""

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


class Assistant(Agent):
    def __init__(
        self,
        sleep_controller: SessionSleepWakeController,
        speaker_identity: SpeakerIdentity,
        speaker_buffer: SpeakerAudioBuffer,
    ) -> None:
        self.sleep_controller = sleep_controller
        self.speaker_identity = speaker_identity
        self.speaker_buffer = speaker_buffer

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
        transcript = getattr(
            new_message,
            "text_content",
            None,
        )

        if callable(transcript):
            transcript = transcript()

        if transcript is None:
            transcript = getattr(
                new_message,
                "raw_text_content",
                "",
            )

        transcript = (
            transcript or ""
        ).strip()

        if not transcript:
            self.speaker_buffer.clear()
            raise StopResponse()

        # ---------------------------------------------------------
        # SPEAKER IDENTIFICATION
        # ---------------------------------------------------------
        print(
            "[L.U.N.A.] Speaker buffer: "
            f"{self.speaker_buffer.debug_state()}"
        )

        pcm_data, sample_rate, num_channels = (
            self.speaker_buffer.get_audio(
                max_seconds=5.0
            )
        )

        speaker_match = await (
            self.speaker_identity.identify_pcm(
                pcm_data=pcm_data,
                sample_rate=sample_rate or 16000,
                num_channels=num_channels or 1,
            )
        )

        self.speaker_buffer.clear()

        print(
            "[L.U.N.A.] Speaker identity: "
            f"{speaker_match.name or 'unknown'} "
            f"({speaker_match.confidence:.2f}) "
            f"authorized={speaker_match.authorized}"
        )

        standby_manager = (
            self.sleep_controller.standby_manager
        )

        # ---------------------------------------------------------
        # STANDBY / WAKE AUTHORIZATION
        # ---------------------------------------------------------

        awaiting_wake = getattr(
            standby_manager,
            "awaiting_speaker_authorization",
            False,
        )

        if awaiting_wake:
            if not speaker_match.authorized:
                print(
                    "[L.U.N.A.] Wake authorization rejected."
                )

                reject_wake = getattr(
                    standby_manager,
                    "reject_wake",
                    None,
                )

                if reject_wake is not None:
                    await reject_wake()

                raise StopResponse()

            print(
                "[L.U.N.A.] Wake authorization accepted: "
                f"{speaker_match.name}"
            )

            complete_wake = getattr(
                standby_manager,
                "complete_wake_authorization",
                None,
            )

            if complete_wake is not None:
                complete_wake()

            # The authorized speaker has now passed identity
            # authorization. Continue processing the wake turn.

        # ---------------------------------------------------------
        # ACTIVE USER AUTHORIZATION
        # ---------------------------------------------------------

        if not speaker_match.authorized:
            print(
                "[L.U.N.A.] Ignoring unauthorized "
                "speaker."
            )

            raise StopResponse()

        # ---------------------------------------------------------
        # NORMAL L.U.N.A. CONTROL
        # ---------------------------------------------------------

        await self.sleep_controller.handle_transcript(
            transcript
        )

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

        full_text = "".join(
            text_parts
        ).strip()

        if not full_text:
            return

        wav_bytes = await asyncio.to_thread(
            synthesize_kokoro,
            full_text,
        )

        for frame in wav_to_audio_frames(
            wav_bytes
        ):
            yield frame


server = AgentServer()


@server.rtc_session(
    agent_name="my-agent"
)
async def my_agent(
    ctx: agents.JobContext,
):
    session = AgentSession(
        stt=groq.STT(),

        vad=silero.VAD.load(
            min_speech_duration=0.05,
            min_silence_duration=0.55,
            prefix_padding_duration=0.5,
            activation_threshold=0.5,
        ),

        turn_handling=TurnHandlingOptions(
            endpointing=EndpointingOptions(
                mode="dynamic",
                min_delay=0.9,
                max_delay=3.0,
                alpha=0.5,
            ),

            interruption=InterruptionOptions(
                enabled=True,
                mode="vad",
                discard_audio_if_uninterruptible=False,
                min_duration=0.50,
                min_words=4,
                resume_false_interruption=True,
                false_interruption_timeout=2.0,
                backchannel_boundary=(0.2, 0.8),
            ),
        ),

        llm=google.LLM(
            model="gemini-3.1-flash-lite",
        ),
    )

    luna_core = LunaCore()

    standby_manager = StandbyManager(
        luna_core=luna_core,
        session=session,
    )

    sleep_controller = SessionSleepWakeController(
        session=session,
        luna_core=luna_core,
        standby_manager=standby_manager,

    )

    try:
        speaker_identity = SpeakerIdentity()

        speaker_buffer = SpeakerAudioBuffer(
            max_seconds=8.0
        )

        speaker_processor = SpeakerIdentity(
            buffer=speaker_buffer,
        )

        await session.start(
            room=ctx.room,
            agent=Assistant(
                sleep_controller=sleep_controller,
                speaker_identity=speaker_identity,
                speaker_buffer=speaker_buffer,
            ),
            room_options=room_io.RoomOptions(
                audio_input=room_io.AudioInputOptions(
                    noise_cancellation=speaker_processor,
                ),
            ),
        )

        print(
            "[L.U.N.A.] Speaker identity processor: ONLINE"
        )

        await session.generate_reply(
            instructions=build_session_instruction(),
        )

    finally:
        await standby_manager.shutdown()


if __name__ == "__main__":
    agents.cli.run_app(server)