import asyncio

from brains.ollama import OllamaProvider
from core.providers import AIRequest


async def main():
    provider = OllamaProvider()

    print("Health:", await provider.health_check())

    response = await provider.generate(
        AIRequest(
            prompt="Introduce yourself to L.U.N.A. in one sentence.",
            task="conversation",
        )
    )

    print("Provider:", response.provider)
    print("Model:", response.model)
    print("Response:", response.text)


if __name__ == "__main__":
    asyncio.run(main())