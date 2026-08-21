import asyncio

from core.providers import AIProvider, AIRequest, AIResponse
from core.router import AIRouter
from core.classifier import TaskClassifier


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


class SessionSleepWakeController:
    """Track L.U.N.A.'s listening state without modifying LiveKit audio yet."""

    def __init__(self, session, luna_core: "LunaCore") -> None:
        self.session = session
        self.luna_core = luna_core

    def handle_transcript(self, transcript: str | None) -> bool:
        text = (transcript or "").strip()

        if not text:
            return self.luna_core.listening

        return self.luna_core.update_listening_state(text)

    def handle_transcription_event(self, event) -> bool:
        transcript = getattr(event, "transcript", None)

        if transcript is None and isinstance(event, str):
            transcript = event
        elif transcript is None:
            transcript = getattr(event, "text", "")

        return self.handle_transcript(transcript)


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
    )

    WAKE_PHRASES = (
        "luna wake up",
        "wake up luna",
        "resume listening",
        "start listening again",
        "you can listen again",
        "back online",
        "come back",
        "luna, wake up",
        "wake up",
    )

    def __init__(self, providers: list[AIProvider]):
        self.router = AIRouter(providers)
        self.classifier = TaskClassifier()
        self.listening = True
        self._warmup_task = None
        self._start_warmup_if_possible()

    def _start_warmup_if_possible(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        if self._warmup_task is None:
            self._warmup_task = loop.create_task(self.warmup_providers())

    def set_listening(self, state: bool) -> bool:
        self.listening = bool(state)
        return self.listening

    def _contains_phrase(self, text: str, phrases: tuple[str, ...]) -> bool:
        lowered = text.lower()
        return any(phrase in lowered for phrase in phrases)

    def update_listening_state(self, prompt: str) -> bool:
        text = (prompt or "").strip()

        if not text:
            return self.listening

        if self._contains_phrase(text, self.SLEEP_PHRASES):
            self.listening = False
            return False

        if self._contains_phrase(text, self.WAKE_PHRASES):
            self.listening = True
            return True

        return self.listening

    async def warmup_providers(self, timeout: float = 3.0) -> None:
        """Warm the providers in the background without blocking startup."""
        for provider in self.router.providers:
            try:
                await asyncio.wait_for(provider.health_check(), timeout=timeout)
            except Exception:
                continue

    async def ask(
        self,
        prompt: str,
        task: str | None = None,
        system_prompt: str | None = None,
    ) -> AIResponse:

        text = (prompt or "").strip()
        if not text:
            return AIResponse(
                text="I didn't hear anything.",
                provider="system",
                model="listening-state",
                metadata={"listening": self.listening},
            )

        if not self.listening:
            if self._contains_phrase(text, self.WAKE_PHRASES):
                self.listening = True
            else:
                return AIResponse(
                    text="Luna is taking a break. Say “Luna, wake up” to resume listening.",
                    provider="system",
                    model="listening-state",
                    metadata={
                        "listening": False,
                        "classified_task": task or "general",
                    },
                )

        if self._contains_phrase(text, self.SLEEP_PHRASES):
            self.listening = False
            return AIResponse(
                text="Luna is taking a break. Say “Luna, wake up” to resume listening.",
                provider="system",
                model="listening-state",
                metadata={
                    "listening": False,
                    "classified_task": task or "general",
                },
            )

        # Automatically classify the request unless
        # the caller explicitly provides a task.
        if task is None:
            classification = self.classifier.classify(prompt)
            task = classification.task

        combined_system_prompt = CORE_SYSTEM_PROMPT

        if system_prompt:
            combined_system_prompt += (
                f"\n\nAdditional instructions:\n{system_prompt}"
            )

        request = AIRequest(
            prompt=prompt,
            task=task,
            system_prompt=combined_system_prompt,
        )

        response = await self.router.generate(request)

        response.metadata.update({
            "classified_task": task,
            "listening": self.listening,
        })

        return response

    async def health_status(self) -> dict[str, bool]:
        """Return the health status of every registered provider."""

        status = {}

        for provider in self.router.providers:
            try:
                status[provider.name] = await provider.health_check()

            except Exception as exc:
                print(
                    f"[L.U.N.A.] Health check failed for "
                    f"'{provider.name}': {exc}"
                )
                status[provider.name] = False

        return status
