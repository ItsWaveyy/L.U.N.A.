import asyncio

from brains.mock import MockProvider
from core.orchestrator import LunaCore
from core.router import AIRouter


class FakeInput:
    def __init__(self):
        self.enabled = True
        self.calls = []

    def set_audio_enabled(self, enabled):
        self.enabled = enabled
        self.calls.append(enabled)


class FakeSession:
    def __init__(self):
        self.input = FakeInput()
        self.handlers = {}

    def on(self, event_name, callback):
        self.handlers[event_name] = callback


async def _run_sleep_wake_session_test():
    from agent import SessionSleepWakeController

    luna = LunaCore([MockProvider()])
    session = FakeSession()
    controller = SessionSleepWakeController(session, luna)

    controller.handle_transcript("that's all for now luna")
    assert not luna.listening
    assert session.input.enabled is True

    controller.handle_transcript("luna, wake up")
    assert luna.listening
    assert session.input.enabled is True


def test_sleep_wake_session_controller():
    asyncio.run(_run_sleep_wake_session_test())


def test_all_sleep_and_wake_phrases():
    luna = LunaCore([MockProvider()])

    for phrase in LunaCore.SLEEP_PHRASES:
        assert luna.update_listening_state(f"LUNA, {phrase}") is False
        assert luna.listening is False

        for wake_phrase in LunaCore.WAKE_PHRASES:
            assert luna.update_listening_state(wake_phrase) is True
            assert luna.listening is True
            luna.set_listening(False)


class RouterForTest(AIRouter):
    TASK_PREFERENCES = {
        "fast": ["mock"],
        "coding": ["mock"],
        "research": ["mock"],
        "creative": ["mock"],
        "conversation": ["mock"],
        "general": ["mock"],
    }


async def main():
    luna = LunaCore([
        MockProvider(),
    ])

    luna.router = RouterForTest([
        MockProvider(),
    ])

    test_cases = [
        ("What is a turbocharger?", "fast"),
        ("Debug this Python error.", "coding"),
        ("What happened in the stock market today?", "research"),
        ("Write me a funny caption.", "creative"),
        ("What do you think about this?", "conversation"),
        ("How do I reset my router?", "general"),
    ]

    print("--- ORCHESTRATOR CLASSIFICATION TEST ---")

    for prompt, expected_task in test_cases:
        response = await luna.ask(prompt)

        actual_task = response.metadata["classified_task"]

        print(
            f"[{'PASS' if actual_task == expected_task else 'FAIL'}] "
            f"{prompt!r} "
            f"→ {actual_task} "
            f"(expected: {expected_task})"
        )

        assert actual_task == expected_task

    print("\n--- EXPLICIT OVERRIDE TEST ---")

    response = await luna.ask(
        "What is a turbocharger?",
        task="research",
    )

    actual_task = response.metadata["classified_task"]

    print(
        f"Override: "
        f"'What is a turbocharger?' "
        f"→ {actual_task}"
    )

    assert actual_task == "research"

    print("\n✅ ORCHESTRATOR TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
