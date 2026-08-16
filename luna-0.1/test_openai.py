import asyncio

from brains.openai import OpenAIProvider
from core.providers import AIRequest


async def main():
    provider = OpenAIProvider()

    print("Provider:", provider.name)
    print("Model:", provider.model)
    print("Checking API health...")

    healthy = await provider.health_check()
    print("Healthy:", healthy)

    if not healthy:
        print("OpenAI API health check failed.")
        return

    response = await provider.generate(
        AIRequest(
            prompt="Respond with exactly: OpenAI brain online.",
            task="general",
        )
    )

    print("Response:", response.text)
    print("Provider:", response.provider)
    print("Model:", response.model)


if __name__ == "__main__":
    asyncio.run(main())