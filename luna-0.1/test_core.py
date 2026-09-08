import asyncio

from brains.gemini import GeminiProvider
from brains.groq import GroqProvider
from brains.ollama import OllamaProvider
from core.orchestrator import LunaCore
from core.registry import ProviderRegistry


async def main():
    registry = ProviderRegistry()

    registry.register(GeminiProvider())
    registry.register(GroqProvider())
    registry.register(OllamaProvider())

    luna = LunaCore(registry.all())

    tests = [
        ("general", "Explain what L.U.N.A. Core is in one sentence."),
        ("conversation", "Say hello to Reece."),
        ("coding", "What Python keyword is used to define a function?"),
        ("research", "What is the capital of France?"),
        ("creative", "Give L.U.N.A. a one-line futuristic motto."),
        ("fast", "What is 2 + 2?"),
    ]

    for task, prompt in tests:
        print(f"\n--- {task.upper()} ---")

        try:
            response = await luna.ask(
                prompt=prompt,
                task=task,
            )

            print(f"Provider: {response.provider}")
            print(f"Model: {response.model}")
            print(f"Response: {response.text}")

        except Exception as e:
            print(f"ERROR: {e}")


asyncio.run(main())