import asyncio

from brains.gemini import GeminiProvider
from brains.groq import GroqProvider
from brains.ollama import OllamaProvider


async def main():
    gemini = GeminiProvider()
    groq = GroqProvider()
    ollama = OllamaProvider()

    print("--- REAL PROVIDER HEALTH TEST ---")

    print(f"Gemini: {'ONLINE' if await gemini.health_check() else 'OFFLINE'}")
    print(f"Groq: {'ONLINE' if await groq.health_check() else 'OFFLINE'}")
    print(f"Ollama: {'ONLINE' if await ollama.health_check() else 'OFFLINE'}")

    await gemini.close()


if __name__ == "__main__":
    asyncio.run(main())