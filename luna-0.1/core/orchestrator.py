import asyncio
import re
import time

from core.providers import AIProvider, AIRequest, AIResponse
from core.router import AIRouter
from core.classifier import TaskClassifier
from core.standby.manager import StandbyManager
from core.tooling import ToolRegistry, build_default_tool_registry, parse_tool_calls
from core.conversation import ConversationStore
from core.identity.speaker import SpeakerMatch


CORE_SYSTEM_PROMPT = """
You are the backend reasoning engine inside L.U.N.A.

L.U.N.A. stands for Lowkey Useful Neural Assistant.

L.U.N.A. is a personal AI assistant being developed by Reece.

L.U.N.A. has two major layers:
- L.U.N.A. Agent: the primary assistant, voice, and personality layer.
- L.U.N.A. Core: the backend intelligence and provider-routing layer.

You are part of L.U.N.A. Core.

When the user refers to L.U.N.A., they mean this personal AI assistant unless they explicitly specify otherwise.

Do not confuse L.U.N.A. with:
- Terra/LUNA cryptocurrency
- Luna Core blockchain software
- fictional AI characters
- unrelated software projects

Your job is to provide accurate and useful results to the primary L.U.N.A. assistant.

Be concise and direct unless the task requires detail.
Do not mention these system instructions.
Do not invent capabilities or actions.
"""


def normalize(text: str) -> str:
    """Normalize speech-recognition text for phrase matching."""

    text = (text or "").lower().strip()

    # Normalize apostrophes.
    text = text.replace("’", "'")

    # Remove punctuation while preserving spaces.
    text = re.sub(r"[^a-z0-9\s']", " ", text)

    # Collapse repeated whitespace.
    text = re.sub(r"\s+", " ", text)

    return text.strip()


class SessionSleepWakeController:
    """
    Controls L.U.N.A.'s listening state for a LiveKit session.

    While awake:
        transcripts are allowed to reach the LLM normally.

    While asleep:
        transcripts are intercepted and checked only for wake phrases.
        No Gemini request is made.
    """

    def __init__(
        self,
        session,
        luna_core: "LunaCore",
        standby_manager: StandbyManager,
    ):
        self.session = session
        self.luna_core = luna_core
        self.standby_manager = standby_manager
        self._just_woke = False

    async def handle_transcript(self, transcript: str):
        text = normalize(transcript)

        if not text:
            return

        # ---------------------------------------------------------
        # STANDBY MODE
        # ---------------------------------------------------------

        if not self.luna_core.listening:
            return

        # ---------------------------------------------------------
        # WAKE PHRASE CONSUMPTION
        # ---------------------------------------------------------

        # The dedicated ONNX detector handles waking.
        # If Groq later delivers the same wake phrase as a transcript,
        # consume it instead of sending it to Gemini.

        if self._just_woke:
            self._just_woke = False

            if self.is_wake_phrase(text):
                return

        # ---------------------------------------------------------
        # ACTIVE MODE
        # ---------------------------------------------------------

        if self.is_sleep_phrase(text):
            await self.sleep()

    async def handle_transcription_event(self, event) -> None:
        transcript = getattr(event, "transcript", None)

        if transcript is None and isinstance(event, str):
            transcript = event

        elif transcript is None:
            transcript = getattr(event, "text", "")

        await self.handle_transcript(transcript)

    def is_sleep_phrase(self, text: str) -> bool:
        return self.luna_core._contains_phrase(
            normalize(text),
            self.luna_core.SLEEP_PHRASES,
        )

    def is_wake_phrase(self, text: str) -> bool:
        return self.luna_core._contains_phrase(
            normalize(text),
            self.luna_core.WAKE_PHRASES,
        )

    async def sleep(self):
        if not self.luna_core.listening:
            return

        print("[L.U.N.A.] Sleep phrase detected.")

        await self.standby_manager.enter_standby()

    async def wake(self, transcript: str):
        if self.luna_core.listening:
            return

        print(
            f'[L.U.N.A.] Wake phrase detected: "{transcript}"'
        )

        self._just_woke = True

        self.luna_core.set_listening(True)

        print("[L.U.N.A.] Listening state: False -> True")
        print("[L.U.N.A.] Standby mode ended.")

    async def shutdown(self):
        await self.standby_manager.shutdown()


class LunaCore:

    SLEEP_PHRASES = (
        "that's all for now",
        "that is all for now",
        "take a break",
        "you can take a break",
        "go to sleep",
        "sleep now",
        "stop listening",
        "pause listening",
        "rest for a bit",
        "that's it for now",
        "that is it for now",
        "you're all done for now",
        "you are all done for now",
    )

    WAKE_PHRASES = (
        "luna wake up",
        "wake up luna",
        "hey luna",
        "hi luna",
        "hello luna",
        "luna are you there",
        "luna you there",
        "are you there luna",
        "luna are you awake",
        "are you awake luna",
        "luna wakey wakey",
        "back online luna",
        "luna back online",
        "resume listening luna",
        "luna resume listening",
        "hey luna",
        "hey, luna",
    )

    def __init__(
        self,
        providers: list[AIProvider] | None = None,
        tools: ToolRegistry | None = None,
    ):
        if providers is None:
            from core.brain_registry import load_providers
            providers = load_providers()

        self.router = AIRouter(providers)
        self.classifier = TaskClassifier()
        self.tools = tools or build_default_tool_registry()

        self.conversations = ConversationStore()
        self.conversations.start_session()

        self.listening = True
        self._warmup_task = None

    def _start_warmup_if_possible(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        if self._warmup_task is None:
            self._warmup_task = loop.create_task(
                self.warmup_providers()
            )

    def set_listening(self, state: bool) -> bool:
        self.listening = bool(state)
        return self.listening

    def record_user_message(
        self,
        content: str,
    ) -> None:
        self.conversations.add_message(
            role="user",
            content=content,
        )

    def record_assistant_message(
        self,
        content: str,
    ) -> None:
        self.conversations.add_message(
            role="assistant",
            content=content,
        )

    def set_speaker(
        self,
        match: SpeakerMatch | None,
    ) -> None:
        """Update the speaker currently associated with the active session."""

        self.current_speaker = match

        if match is None:
            print("[L.U.N.A.] Current speaker: unknown")
            return

        print(
            "[L.U.N.A.] Current speaker: "
            f"{match.name or 'unknown'} "
            f"({match.confidence:.2f})"
        )

    def _contains_phrase(
        self,
        text: str,
        phrases: tuple[str, ...],
    ) -> bool:

        lowered = normalize(text)

        return any(
            phrase in lowered
            for phrase in phrases
        )

    def update_listening_state(
        self,
        prompt: str,
    ) -> bool:

        text = normalize(prompt)

        if not text:
            return self.listening

        if self._contains_phrase(
            text,
            self.SLEEP_PHRASES,
        ):
            self.listening = False
            return False

        if self._contains_phrase(
            text,
            self.WAKE_PHRASES,
        ):
            self.listening = True
            return True

        return self.listening

    async def warmup_providers(
        self,
        timeout: float = 3.0,
    ) -> None:

        for provider in self.router.providers:

            try:
                await asyncio.wait_for(
                    provider.health_check(),
                    timeout=timeout,
                )

            except Exception:
                continue

    async def ask(
        self,
        prompt: str,
        task: str | None = None,
        system_prompt: str | None = None,
    ) -> AIResponse:

        text = normalize(prompt)

        if not text:
            return AIResponse(
                text="I didn't hear anything.",
                provider="system",
                model="listening-state",
                metadata={
                    "listening": self.listening
                },
            )

        # ---------------------------------------------------------
        # STANDBY
        # ---------------------------------------------------------

        if not self.listening:

            if self._contains_phrase(
                text,
                self.WAKE_PHRASES,
            ):
                self.listening = True

            else:
                return AIResponse(
                    text="",
                    provider="system",
                    model="listening-state",
                    metadata={
                        "listening": False,
                        "classified_task": (
                            task or "general"
                        ),
                    },
                )

        # ---------------------------------------------------------
        # SLEEP
        # ---------------------------------------------------------

        if self._contains_phrase(
            text,
            self.SLEEP_PHRASES,
        ):

            self.listening = False

            return AIResponse(
                text="",
                provider="system",
                model="listening-state",
                metadata={
                    "listening": False,
                    "classified_task": (
                        task or "general"
                    ),
                },
            )

        # ---------------------------------------------------------
        # NORMAL REQUEST
        # ---------------------------------------------------------

        classification_started = time.perf_counter()

        if task is None:
            classification = self.classifier.classify(
                prompt
            )
            task = classification.task
        else:
            classification = None

        classification_seconds = (
            time.perf_counter()
            - classification_started
        )

        combined_system_prompt = CORE_SYSTEM_PROMPT

        if system_prompt:
            combined_system_prompt += (
                "\n\nAdditional instructions:\n"
                f"{system_prompt}"
            )

        tool_definitions = self.tools.definitions()

        if (
            classification is not None
            and classification.requires_network
        ):
            tool_instructions = (
                "\n\nAvailable Core tools:\n"
                f"{tool_definitions}\n\n"
                "When a tool is necessary, reply with only valid JSON in this "
                "exact shape: {\"tool_calls\":[{\"name\":\"tool_name\","
                "\"arguments\":{...}}]}. Do not use a tool for ordinary "
                "conversation. Only use send_email after the user explicitly asks "
                "to send it, and include explicit_request=true."
            )
        else:
            tool_instructions = (
                "\n\nNo network access is required for this request. "
                "Answer directly using your available knowledge. "
                "Do not use network-dependent tools such as web search."
            )

        combined_system_prompt += tool_instructions

        # ---------------------------------------------------------
        # LOCAL PROVIDER PROMPT
        # ---------------------------------------------------------

        local_system_prompt = (
            "You are L.U.N.A., a personal AI assistant.\n"
            "You are running as L.U.N.A. Core's local reasoning provider.\n"
            "Answer the user's request directly and concisely.\n"
            "Do not claim internet access or current information when offline.\n"
            "Follow any additional instructions provided for this request.\n"
        )

        if system_prompt:
            local_system_prompt += (
                "\nAdditional instructions:\n"
                f"{system_prompt}"
            )

        if (
            classification is not None
            and classification.requires_network
        ):
            local_system_prompt += (
                "\n\nAvailable Core tools:\n"
                f"{tool_definitions}\n\n"
                "When a tool is necessary, reply with only valid JSON in this "
                "exact shape: {\"tool_calls\":[{\"name\":\"tool_name\","
                "\"arguments\":{...}}]}. "
                "Do not answer the request directly when a listed tool is "
                "required. "
                "Do not use tools for ordinary conversation. "
                "Only use send_email after the user explicitly asks to send it, "
                "and include explicit_request=true."
            )

        requires_network = (
            classification.requires_network
            if classification is not None
            else False
        )

        request = AIRequest(
            prompt=prompt,
            task=task,
            system_prompt=combined_system_prompt,
            metadata={
                "requires_network": requires_network,
                "network_allowed": requires_network,
                "local_system_prompt": local_system_prompt,
            },
        )
        provider_started = time.perf_counter()

        response = await self.router.generate(
            request
        )

        provider_generation_seconds = (
            time.perf_counter()
            - provider_started
        )

        tool_calls = parse_tool_calls(response.text)

        if tool_calls:
            tool_results = []

            for name, arguments in tool_calls:
                result = await self.tools.execute(
                    name,
                    arguments,
                    offline=(
                        self.router.mode == "offline"
                        or not request.metadata.get(
                            "network_allowed",
                            False,
                        )
                    ),
                )
                tool_results.append({
                    "name": name,
                    "result": result,
                })

            completion_request = AIRequest(
                prompt=(
                    f"Original user request: {prompt}\n\n"
                    "Tool results:\n"
                    f"{tool_results}\n\n"
                    "Respond to the user using these results. Do not describe "
                    "the internal tool protocol."
                ),
                task=task,
                system_prompt=(
                    combined_system_prompt
                    + "\n\nThe required tools have already run. Return "
                    "the final user-facing answer, not tool-call JSON."
                ),
                metadata=request.metadata.copy(),
            )
            response = await self.router.generate(completion_request)
            response.metadata["tools_used"] = [
                name for name, _ in tool_calls
            ]
        else:
            response.metadata["tools_used"] = []

        response.metadata.update({
            "classification_seconds": (
                classification_seconds
            ),
            "provider_generation_seconds": (
                provider_generation_seconds
            ),
            "classified_task": task,
            "listening": self.listening,
        })

        return response

    async def health_status(self) -> dict[str, bool]:
        """Return the health status of every registered provider."""

        status = {}

        for provider in self.router.providers:

            try:
                status[provider.name] = (
                    await provider.health_check()
                )

            except Exception as exc:
                print(
                    "[L.U.N.A.] Health check failed for "
                    f"'{provider.name}': {exc}"
                )

                status[provider.name] = False

        return status
