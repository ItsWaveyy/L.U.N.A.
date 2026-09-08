import asyncio

from core.providers import AIRequest
from core.router import AIRouter
from brains.mock import MockProvider


class TestRouter(AIRouter):
    TASK_PREFERENCES = {
        task: ["mock"]
        for task in ("coding", "research", "conversation", "general")
    }


async def main():
    router = TestRouter([MockProvider()])

    tasks = [
        "coding",
        "research",
        "conversation",
        "general",
    ]

    for task in tasks:
        print(f"\n--- {task.upper()} ---")

        response = await router.generate(
            AIRequest(
                prompt=f"Test {task} request",
                task=task,
            )
        )

        print("Response:", response.text)
        print("Provider:", response.provider)


if __name__ == "__main__":
    asyncio.run(main())