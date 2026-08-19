import asyncio

from brains.mock import MockProvider
from core.orchestrator import LunaCore
from core.router import AIRouter


class TestRouter(AIRouter):
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

    luna.router = TestRouter([
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
