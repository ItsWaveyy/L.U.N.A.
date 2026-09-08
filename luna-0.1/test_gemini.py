import asyncio
import time

from brains.gemini import GeminiProvider
from core.providers import AIRequest


async def main():
    start = time.perf_counter()

    provider = GeminiProvider()

    print(f"Provider initialized in {time.perf_counter() - start:.2f}s")

    response = await provider.generate(
        AIRequest(
            prompt="Say hello to L.U.N.A. in one short sentence.",
            task="general",
        )
    )

    print()
    print("Provider:", response.provider)
    print("Model:", response.model)
    print("Response:", response.text)

    await provider.close()


asyncio.run(main())