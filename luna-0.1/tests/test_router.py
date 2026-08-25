import asyncio

from core.providers import AIRequest
from core.providers.gemini import GeminiProvider
from core.providers.groq import GroqProvider
from core.router import AIRouter


async def main():
    providers = [
        GeminiProvider(),
        GroqProvider(),
    ]

    router = AIRouter(providers)

    tests = [
        ("fast", "What is 2 + 2?"),
        ("coding", "Write a Python function that reverses a string."),
        ("research", "What are the latest developments in AI?"),
        ("creative", "Come up with a badass name for a BMW build."),
        ("conversation", "What do you think about cars?"),
        ("general", "Tell me something interesting."),
    ]

    for task, prompt in tests:
        print()
        print("=" * 60)
        print(f"TASK: {task}")
        print(f"PROMPT: {prompt}")
        print("=" * 60)

        request = AIRequest(
            prompt=prompt,
            task=task,
        )

        response = await router.generate(request)

        print(f"PROVIDER: {response.provider}")
        print(f"MODEL: {response.model}")
        print(f"RESPONSE: {response.text}")
        print(f"METADATA: {response.metadata}")


if __name__ == "__main__":
    asyncio.run(main())