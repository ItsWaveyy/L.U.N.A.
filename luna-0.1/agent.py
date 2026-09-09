import asyncio
import time
from typing import AsyncGenerator

from dotenv import load_dotenv

from livekit import agents
from livekit.agents import (
    AgentServer,
    AgentSession,
    Agent,
    room_io,
    TurnHandlingOptions,
    EndpointingOptions,
    InterruptionOptions,
    StopResponse,
    llm,
)
from livekit.plugins import ai_coustics, groq
from livekit.plugins import silero

from core.orchestrator import SessionSleepWakeController
from core.client import CoreClient
from core.standby.manager import StandbyManager
from core.identity.audio import (
    SpeakerAudioBuffer,
    SpeakerIdentityProcessor,
)
from core.identity.speaker import SpeakerIdentity
from core.timing import (
    TurnTiming,
    log_turn_timing,
    luna_log,
)
from core.tts.kokoro import KokoroTTS

from prompts import AGENT_INSTRUCTION, build_session_instruction
from tools.memory import initialize_database


load_dotenv()
initialize_database()


# ============================================================
# LIVEKIT FRAMEWORK PLACEHOLDER
# ============================================================


class PlaceholderLLM(llm.LLM):
    """
    Framework-only placeholder LLM.

    L.U.N.A. does NOT use this model for actual generation.

    LiveKit requires AgentSession to have an LLM object
    attached before generation can occur.

    Actual L.U.N.A. generation happens through:

        Assistant.llm_node()
            ↓
        CoreClient.ask()
            ↓
        L.U.N.A. Core API
            ↓
        LunaCore
            ↓
        Router
            ↓
        Provider
    """

    def chat(
        self,
        *args,
        **kwargs,
    ):
        raise RuntimeError(
            "PlaceholderLLM.chat() was called directly. "
            "L.U.N.A. should route generation through "
            "Assistant.llm_node()."
        )


# ============================================================
# LIVEKIT ASSISTANT
# ============================================================


class Assistant(Agent):
    """
    LiveKit-facing voice interface.

    This class does not own L.U.N.A.'s persistent runtime.

    It translates LiveKit conversation events into calls
    to the persistent L.U.N.A. Core through CoreClient.
    """

    def __init__(
        self,
        sleep_controller: SessionSleepWakeController,
        luna_core: CoreClient,
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

            text = (
                message.text_content or ""
            ).strip()

            if text:
                return text

        return ""

    @staticmethod
    def _conversation_context(chat_ctx) -> str:
        """
        Render recent text turns for providers that accept
        a flat prompt.

        Kept for compatibility with the existing voice layer.
        """

        turns = []

        for message in chat_ctx.messages()[-8:]:

            if message.role not in {
                "user",
                "assistant",
            }:
                continue

            text = (
                message.text_content or ""
            ).strip()

            if text:
                turns.append(
                    f"{message.role.title()}: {text}"
                )

        return "\n".join(turns)

    async def llm_node(
        self,
        chat_ctx,
        tools,
        model_settings,
    ) -> AsyncGenerator[str, None]:
        """
        Route LiveKit responses through the persistent Core API.
        """

        prompt = self._latest_user_message(
            chat_ctx
        )

        if not prompt:
            return

        timing = TurnTiming()

        luna_log(
            "Routing request through Core: "
            f"{prompt}"
        )

        timing.started_at = time.perf_counter()

        core_started = time.perf_counter()

        response = await self.luna_core.ask(
            prompt=prompt,
            system_prompt=AGENT_INSTRUCTION,
        )

        core_total = (
            time.perf_counter()
            - core_started
        )

        timing.add(
            "core_total",
            core_total,
        )

        self.last_core_response = response

        metadata = response.metadata

        if metadata.get(
            "classification_seconds"
        ) is not None:

            timing.add(
                "classification",
                metadata[
                    "classification_seconds"
                ],
            )

        if metadata.get(
            "provider_generation_seconds"
        ) is not None:

            timing.add(
                "provider_generation",
                metadata[
                    "provider_generation_seconds"
                ],
            )

        luna_log(
            "Core response: "
            f"provider={response.provider} "
            f"model={response.model} "
            f"task={metadata.get('classified_task')} "
            f"latency={core_total:.3f}s"
        )

        if metadata.get("fallback_used"):

            luna_log(
                "Core fallback: "
                f"{metadata.get('fallback_from')} "
                "-> "
                f"{response.provider}"
            )

        if response.text:

            await self.luna_core.record_assistant_message(
                response.text
            )

            yield response.text

        log_turn_timing(timing)

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

        await self.luna_core.record_user_message(
            transcript
        )

        await self.sleep_controller.handle_transcript(
            transcript
        )

        if not self.luna_core.listening:
            raise StopResponse()


# ============================================================
# LIVEKIT SERVER
# ============================================================


server = AgentServer()


# ============================================================
# LIVEKIT SESSION
# ============================================================


@server.rtc_session(
    agent_name="L.U.N.A.",
)
async def my_agent(
    ctx: agents.JobContext,
):

    # --------------------------------------------------------
    # LIVEKIT SESSION
    # --------------------------------------------------------

    session = AgentSession(

        # LiveKit framework requirement.
        llm=PlaceholderLLM(),

        # Voice output.
        tts=KokoroTTS(),

        # Speech-to-text.
        stt=groq.STT(),

        # Voice activity detection.
        vad=silero.VAD.load(
            min_speech_duration=0.05,
            min_silence_duration=0.55,
            prefix_padding_duration=0.5,
            activation_threshold=0.5,
        ),

        # Turn handling.
        turn_handling=TurnHandlingOptions(

            endpointing=EndpointingOptions(
                mode="dynamic",
                min_delay=0.45,
                max_delay=1.5,
                alpha=0.35,
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

    # --------------------------------------------------------
    # PERSISTENT CORE ACCESS
    # --------------------------------------------------------
    #
    # The LiveKit agent does NOT create or own LunaCore.
    #
    # CoreClient communicates with the persistent
    # LunaCoreRuntime through the Core API.
    # --------------------------------------------------------

    luna_core = CoreClient()

    # --------------------------------------------------------
    # LIVEKIT ACCESS-POINT SERVICES
    # --------------------------------------------------------

    standby_manager = StandbyManager(
        luna_core=luna_core,
        session=session,
    )

    sleep_controller = SessionSleepWakeController(
        session=session,
        luna_core=luna_core,
        standby_manager=standby_manager,
    )

    # --------------------------------------------------------
    # SPEAKER IDENTITY / AUDIO PIPELINE
    # --------------------------------------------------------

    speaker_identity = SpeakerIdentity()

    speaker_buffer = SpeakerAudioBuffer(
        max_seconds=8.0,
    )

    ai_coustics_processor = (
        ai_coustics.audio_enhancement()
    )

    def on_speaker_identified(match):
        asyncio.create_task(
            luna_core.set_speaker(match)
        )

    speaker_processor = SpeakerIdentityProcessor(
        buffer=speaker_buffer,
        speaker_identity=speaker_identity,
        downstream=ai_coustics_processor,
        on_identified=on_speaker_identified,
    )

    # --------------------------------------------------------
    # SESSION CLEANUP
    # --------------------------------------------------------

    async def cleanup():

        luna_log(
            "LiveKit session shutdown: "
            "stopping standby manager..."
        )

        await standby_manager.shutdown()

        luna_log(
            "LiveKit session shutdown: "
            "standby manager stopped."
        )

        luna_log(
            "LiveKit session shutdown: "
            "Core remains online."
        )

    def on_session_close(event):
        asyncio.create_task(
            cleanup()
        )

    session.on(
        "close",
        on_session_close,
    )

    # --------------------------------------------------------
    # START LIVEKIT SESSION
    # --------------------------------------------------------

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

    session.input.set_audio_enabled(False)

    luna_log(
        "Speaker identity processor: ONLINE"
    )

    # --------------------------------------------------------
    # STARTUP GREETING
    # --------------------------------------------------------

    luna_log(
        "Generating startup greeting through Core..."
    )

    startup_timing = TurnTiming()

    startup_instruction = (
        build_session_instruction()
    )

    luna_log(
        "Startup prompt loaded from prompts.py."
    )

    startup_core_started = (
        time.perf_counter()
    )

    startup_response = await luna_core.ask(
        prompt=startup_instruction,
        system_prompt=AGENT_INSTRUCTION,
    )

    startup_core_seconds = (
        time.perf_counter()
        - startup_core_started
    )

    startup_timing.add(
        "core_generation",
        startup_core_seconds,
    )

    luna_log(
        "Startup Core response: "
        f"provider={startup_response.provider} "
        f"model={startup_response.model} "
        f"latency={startup_core_seconds:.3f}s"
    )

    if startup_response.text:

        luna_log(
            "Startup greeting: "
            f"{startup_response.text}"
        )

        await session.say(
            startup_response.text
        )

    session.input.set_audio_enabled(True)

    log_turn_timing(
        startup_timing
    )


# ============================================================
# ENTRYPOINT
# ============================================================


if __name__ == "__main__":
    agents.cli.run_app(server)