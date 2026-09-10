import asyncio
import re
import time
from pathlib import Path

from core.providers import AIProvider, AIRequest, AIResponse
from core.router import AIRouter
from core.classifier import TaskClassifier
from core.standby.manager import StandbyManager
from core.tooling import ToolRegistry, build_default_tool_registry, parse_tool_calls
from core.conversation import ConversationStore
from core.identity.speaker import SpeakerMatch
from core.improvement.manager import ImprovementManager
from core.improvement.pipeline import ImprovementPipeline
from core.dashboard.activity import ActivityManager
from core.dashboard.runtime_state import CoreRuntimeState


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
            if self.is_wake_phrase(text):
                await self.wake(transcript)
            return

        # ---------------------------------------------------------
        # WAKE PHRASE CONSUMPTION
        # ---------------------------------------------------------

        # The dedicated ONNX detector handles waking.
        # If Groq later delivers the same wake phrase as a transcript,
        # consume it instead of sending it to the LLM.

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
        self.activity: ActivityManager | None = None
        self.runtime_state: CoreRuntimeState | None = None
        self.conversations = ConversationStore()

        # ---------------------------------------------------------
        # SELF-IMPROVEMENT
        # ---------------------------------------------------------

        self.repository_root = (
            Path(__file__).resolve().parent.parent
        )

        improvement_manager = ImprovementManager(
            plans_directory=(
                self.repository_root
                / "data"
                / "improvement"
                / "plans"
            )
        )

        self.improvement = ImprovementPipeline(
            repository_root=str(
                self.repository_root
            ),
            manager=improvement_manager,
        )

        self.listening = True
        self.current_speaker: SpeakerMatch | None = None
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

    def _is_reminder_request(self, text: str) -> bool:
        """Return True when the user explicitly asks L.U.N.A. to create a reminder."""

        text = normalize(text)

        reminder_keywords = (
            "remind me",
            "set a reminder",
            "set me a reminder",
            "reminder",
            "remember to remind me",
        )

        return any(
            keyword in text
            for keyword in reminder_keywords
        )

    def _create_relative_reminder(
        self,
        prompt: str,
    ) -> AIResponse | None:
        """
        Handle simple explicit relative-time reminders deterministically.

        Supported examples:
            remind me in 30 seconds that ...
            remind me in 5 minutes to ...
            remind me in 2 hours that ...
        """

        text = normalize(prompt)

        pattern = re.compile(
            r"""
            \bremind\s+me
            \s+in\s+
            (?P<amount>\d+)
            \s+
            (?P<unit>second|seconds|minute|minutes|hour|hours)
            \s+
            (?P<message>.+?)
            \s*[.!?]?
            $
            """,
            re.IGNORECASE | re.VERBOSE,
        )

        match = pattern.search(text)

        if not match:
            return None

        amount = int(match.group("amount"))
        unit = match.group("unit").lower()
        message = match.group("message").strip()

        if not message:
            return None

        multipliers = {
            "second": 1,
            "seconds": 1,
            "minute": 60,
            "minutes": 60,
            "hour": 3600,
            "hours": 3600,
        }

        seconds = amount * multipliers[unit]

        from datetime import datetime, timedelta

        remind_at = datetime.now().astimezone() + timedelta(
            seconds=seconds
        )

        reminder_id = self.conversations.add_reminder(
            message=message,
            remind_at=remind_at,
        )

        local_time = remind_at.strftime(
            "%A, %B %-d at %-I:%M:%S %p"
        )

        return AIResponse(
            text=(
                f"Got it, sir. I'll remind you "
                f"at {local_time}."
            ),
            provider="core",
            model="reminder-scheduler",
            metadata={
                "reminder_created": True,
                "reminder_id": reminder_id,
                "reminder_message": message,
                "reminder_seconds": seconds,
            },
        )

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

    def set_activity_manager(
        self,
        activity: ActivityManager,
    ) -> None:
        self.activity = activity

    def set_runtime_state(
        self,
        runtime_state: CoreRuntimeState,
    ) -> None:
        self.runtime_state = runtime_state

    async def ask(
        self,
        prompt: str,
        task: str | None = None,
        system_prompt: str | None = None,
    ) -> AIResponse:

        request_started = time.perf_counter()

        text = normalize(prompt)

        # ---------------------------------------------------------
        # RUNTIME STATE — REQUEST RECEIVED
        # ---------------------------------------------------------

        if self.runtime_state is not None:
            self.runtime_state.record_request(
                prompt=prompt,
                task=task,
            )

        if not text:
            response = AIResponse(
                text="I didn't hear anything.",
                provider="system",
                model="listening-state",
                metadata={
                    "listening": self.listening,
                },
            )

            if self.runtime_state is not None:
                self.runtime_state.record_response(
                    provider=response.provider,
                    model=response.model,
                    latency_seconds=(
                        time.perf_counter() - request_started
                    ),
                )

            return response

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
                response = AIResponse(
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

                if self.runtime_state is not None:
                    self.runtime_state.record_response(
                        provider=response.provider,
                        model=response.model,
                        latency_seconds=(
                            time.perf_counter()
                            - request_started
                        ),
                    )

                return response

        # ---------------------------------------------------------
        # SLEEP
        # ---------------------------------------------------------

        if self._contains_phrase(
            text,
            self.SLEEP_PHRASES,
        ):

            self.listening = False

            response = AIResponse(
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

            if self.runtime_state is not None:
                self.runtime_state.record_response(
                    provider=response.provider,
                    model=response.model,
                    latency_seconds=(
                        time.perf_counter()
                        - request_started
                    ),
                )

            return response

        # ---------------------------------------------------------
        # REMINDERS
        # ---------------------------------------------------------

        if self._is_reminder_request(text):
            reminder_response = self._create_relative_reminder(
                prompt
            )

            if reminder_response is not None:
                reminder_response.metadata.update({
                    "classified_task": "fast",
                    "listening": self.listening,
                    "classification_seconds": 0.0,
                    "provider_generation_seconds": 0.0,
                    "tools_used": ["create_reminder"],
                })

                total_seconds = (
                    time.perf_counter()
                    - request_started
                )

                reminder_response.metadata[
                    "core_total_seconds"
                ] = total_seconds

                if self.runtime_state is not None:
                    self.runtime_state.begin_routing(
                        task="fast",
                        provider="core",
                        model="reminder-scheduler",
                    )

                    self.runtime_state.complete_routing(
                        task="fast",
                        provider="core",
                        model="reminder-scheduler",
                        fallback_used=False,
                        fallback_from=None,
                        latency_seconds=total_seconds,
                    )

                    self.runtime_state.record_response(
                        provider="core",
                        model="reminder-scheduler",
                        latency_seconds=total_seconds,
                    )

                if self.activity is not None:
                    self.activity.record(
                        event_type="reminder",
                        message="Created a reminder.",
                        task="fast",
                        provider="core",
                        model="reminder-scheduler",
                        latency_seconds=total_seconds,
                        fallback_used=False,
                        fallback_from=None,
                    )

                return reminder_response

        # ---------------------------------------------------------
        # CLASSIFICATION
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

        # ---------------------------------------------------------
        # RUNTIME STATE — ROUTING STARTED
        # ---------------------------------------------------------

        if self.runtime_state is not None:
            self.runtime_state.begin_routing(
                task=task,
            )

        # ---------------------------------------------------------
        # SYSTEM PROMPT
        # ---------------------------------------------------------

        combined_system_prompt = CORE_SYSTEM_PROMPT

        if system_prompt:
            combined_system_prompt += (
                "\n\nAdditional instructions:\n"
                f"{system_prompt}"
            )

        tool_definitions = self.tools.definitions()

        local_tool_request = (
            classification is not None
            and task == "fast"
            and not classification.requires_network
            and any(
                keyword in text
                for keyword in (
                    "inspect yourself",
                    "inspect self",
                    "inspect your repository",
                    "inspect the repository",
                    "inspect your code",
                    "inspect your codebase",
                    "look at yourself",
                    "look at your code",
                    "review yourself",
                    "review your code",
                    "review your codebase",
                    "analyze yourself",
                    "analyze your code",
                    "analyze your codebase",
                    "check yourself",
                    "check your code",
                    "check your codebase",
                )
            )
        )

        if (
            classification is not None
            and (
                classification.requires_network
                or local_tool_request
            )
        ):
            tool_instructions = (
                "\n\nAvailable Core tools:\n"
                f"{tool_definitions}\n\n"
                "When a tool is necessary, reply with only valid JSON in this "
                "exact shape: {\"tool_calls\":[{\"name\":\"tool_name\","
                "\"arguments\":{...}}]}. Do not use a tool for ordinary "
                "conversation. Only use send_email after the user explicitly "
                "asks to send it, and include explicit_request=true."
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
            and (
                classification.requires_network
                or local_tool_request
            )
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

        # ---------------------------------------------------------
        # PROVIDER GENERATION
        # ---------------------------------------------------------

        provider_started = time.perf_counter()

        response = await self.router.generate(
            request
        )

        provider_generation_seconds = (
            time.perf_counter()
            - provider_started
        )

        # ---------------------------------------------------------
        # TOOL EXECUTION
        # ---------------------------------------------------------

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

            # -----------------------------------------------------
            # TOOL COMPLETION GENERATION
            # -----------------------------------------------------

            completion_started = time.perf_counter()

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

            response = await self.router.generate(
                completion_request
            )

            completion_seconds = (
                time.perf_counter()
                - completion_started
            )

            provider_generation_seconds += completion_seconds

            response.metadata["tools_used"] = [
                name for name, _ in tool_calls
            ]

        else:
            response.metadata["tools_used"] = []

        # ---------------------------------------------------------
        # FINAL METADATA
        # ---------------------------------------------------------

        core_total_seconds = (
            time.perf_counter()
            - request_started
        )

        response.metadata.update({
            "classification_seconds": (
                classification_seconds
            ),
            "provider_generation_seconds": (
                provider_generation_seconds
            ),
            "core_total_seconds": (
                core_total_seconds
            ),
            "classified_task": task,
            "listening": self.listening,
        })

        # ---------------------------------------------------------
        # RUNTIME STATE — ROUTING COMPLETED
        # ---------------------------------------------------------

        if self.runtime_state is not None:
            metadata = response.metadata

            self.runtime_state.complete_routing(
                task=task,
                provider=response.provider,
                model=response.model,
                fallback_used=bool(
                    metadata.get("fallback_used")
                ),
                fallback_from=metadata.get(
                    "fallback_from"
                ),
                latency_seconds=core_total_seconds,
            )

            self.runtime_state.record_response(
                provider=response.provider,
                model=response.model,
                latency_seconds=core_total_seconds,
            )

        # ---------------------------------------------------------
        # ACTIVITY
        # ---------------------------------------------------------

        if self.activity is not None:
            metadata = response.metadata

            self.activity.record(
                event_type="request",
                message=f"Completed request through {response.provider}.",
                task=metadata.get("classified_task"),
                provider=response.provider,
                model=response.model,
                latency_seconds=core_total_seconds,
                fallback_used=bool(
                    metadata.get("fallback_used")
                ),
                fallback_from=metadata.get(
                    "fallback_from"
                ),
            )

        return response

    # -------------------------------------------------------------
    # SELF-IMPROVEMENT API
    # -------------------------------------------------------------

    def inspect_repository(self):
        """
        Perform a read-only inspection of L.U.N.A.'s repository.

        This operation cannot modify source code.
        """

        return self.improvement.inspect()

    def create_improvement_plan(
        self,
        *,
        title: str,
        objective: str,
        summary: str = "",
        reasoning: str = "",
        changes=None,
        tests=None,
        risks=None,
        rollback_strategy: str = "",
    ):
        """
        Create a draft self-improvement plan.

        Creating a plan never approves or executes it.
        """

        return self.improvement.create_plan(
            title=title,
            objective=objective,
            summary=summary,
            reasoning=reasoning,
            changes=changes,
            tests=tests,
            risks=risks,
            rollback_strategy=rollback_strategy,
        )

    def request_improvement_approval(
        self,
        plan_id: str,
    ):
        """
        Mark a draft improvement plan as awaiting user approval.
        """

        return self.improvement.request_approval(
            plan_id
        )

    def approve_improvement_plan(
        self,
        plan_id: str,
    ):
        """
        Explicitly approve an improvement plan.

        Approval and execution intentionally remain separate.
        """

        return self.improvement.approve(
            plan_id
        )

    def reject_improvement_plan(
        self,
        plan_id: str,
    ):
        """Reject an improvement plan."""

        return self.improvement.reject(
            plan_id
        )

    def execute_improvement_plan(
        self,
        plan_id: str,
        *,
        file_contents: dict[str, str],
    ):
        """
        Execute an already-approved improvement plan.

        The ChangeExecutor and ImprovementSafetyPolicy enforce
        repository and path safety.
        """

        return self.improvement.execute(
            plan_id,
            file_contents=file_contents,
        )

    def test_improvement_plan(
        self,
        plan_id: str,
        test_callback,
    ):
        """
        Test an executed improvement plan using a caller-supplied
        safe callback.

        Arbitrary shell execution is not exposed here.
        """

        return self.improvement.test(
            plan_id,
            test_callback,
        )

    def get_improvement_plan(
        self,
        plan_id: str,
    ):
        """Retrieve a persisted improvement plan."""

        return self.improvement.get_plan(
            plan_id
        )

    def list_improvement_plans(self):
        """Return all persisted self-improvement plans."""

        return self.improvement.manager.list_plans()

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