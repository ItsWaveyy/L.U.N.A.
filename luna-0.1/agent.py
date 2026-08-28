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
    TurnHandlingOptions,
    EndpointingOptions,
    InterruptionOptions,
)
from livekit.agents.llm import StopResponse
from livekit.plugins import ai_coustics, groq
from livekit.plugins import silero

from core.orchestrator import LunaCore, SessionSleepWakeController
from core.standby.manager import StandbyManager
from core.identity.audio import (
    SpeakerAudioBuffer,
    SpeakerIdentityProcessor,
)
from core.identity.speaker import SpeakerIdentity

from prompts import AGENT_INSTRUCTION, build_session_instruction
from tools.memory import initialize_database


KOKORO_URL = "http://127.0.0.1:8880"
KOKORO_VOICE = "af_heart"


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
        luna_core: LunaCore,
    ) -> None:
        self.sleep_controller = sleep_controller
        self.luna_core = luna_core
        self.last_core_response = None

        super().__init__(
            instructions=AGENT_INSTRUCTION,
        )

    @staticmethod
    def _latest_user_message(chat_ctx) -> str:
        """Return the newest text message spoken by the user."""

        for message in reversed(chat_ctx.messages()):
            if message.role != "user":
                continue

            text = (message.text_content or "").strip()

            if text:
                return text

        return ""

    @staticmethod
    def _conversation_context(chat_ctx) -> str:
        """Render recent text turns for providers that accept a flat prompt."""

        turns = []

        for message in chat_ctx.messages()[-8:]:
            if message.role not in {"user", "assistant"}:
                continue

            text = (message.text_content or "").strip()

            if text:
                turns.append(f"{message.role.title()}: {text}")

        return "\n".join(turns)

    async def llm_node(
        self,
        chat_ctx,
        tools,
        model_settings,
    ) -> str:
        """Generate every normal live reply through the Core router.

        LiveKit owns the realtime turn lifecycle, while LunaCore owns task
        classification, provider selection, offline policy, and fallback.
        """

        prompt = self._latest_user_message(chat_ctx)

        if not prompt:
            return ""

        conversation = self._conversation_context(chat_ctx)
        system_prompt = AGENT_INSTRUCTION

        if conversation:
            system_prompt += (
                "\n\nRecent conversation for continuity:\n"
                f"{conversation}"
            )

        response = await self.luna_core.ask(
            prompt=prompt,
            system_prompt=system_prompt,
        )

        self.last_core_response = response

        print(
            "[L.U.N.A.] Core response: "
            f"provider={response.provider} model={response.model} "
            f"task={response.metadata.get('classified_task')}"
        )

        return response.text

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
            raise StopResponse()

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
        """Convert Core-generated text into L.U.N.A.'s Kokoro voice."""

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

            preemptive_generation={
                "enabled": False,
            },
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
            max_seconds=8.0,
        )

        ai_coustics_processor = (
            ai_coustics.audio_enhancement()
        )

        speaker_processor = SpeakerIdentityProcessor(
            buffer=speaker_buffer,
            speaker_identity=speaker_identity,
            downstream=ai_coustics_processor,
        )

        await session.start(
            room=ctx.room,
            agent=Assistant(
                sleep_controller=sleep_controller,
                luna_core=luna_core,
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
