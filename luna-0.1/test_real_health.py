import asyncio

from brains.gemini import GeminiProvider
from brains.ollama import OllamaProvider


async def main():
    gemini = GeminiProvider()
    ollama = OllamaProvider()

    print("--- REAL PROVIDER HEALTH TEST ---")

    print(
        f"Gemini: "
        f"{'ONLINE' if await gemini.health_check() else 'OFFLINE'}"
    )

    print(
        f"Ollama: "
        f"{'ONLINE' if await ollama.health_check() else 'OFFLINE'}"
    )

    await gemini.close()


if __name__ == "__main__":
    asyncio.run(main())