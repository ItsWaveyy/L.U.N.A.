import asyncio

from brains.groq import GroqProvider
from core.providers import AIRequest


async def main():
    groq = GroqProvider()

    print("Testing Groq health...")
    healthy = await groq.health_check()

    print(f"Groq health: {'ONLINE' if healthy else 'OFFLINE'}")

    if not healthy:
        return

    print("\nTesting generation...")

    response = await groq.generate(
        AIRequest(
            prompt="Explain why the sky is blue in two sentences.",
            task="general",
            system_prompt=(
                "You are L.U.N.A.'s backend reasoning engine. "
                "Be concise and direct."
            ),
        )
    )

    print("\nProvider:", response.provider)
    print("Model:", response.model)
    print("Response:", response.text)


if __name__ == "__main__":
    asyncio.run(main())