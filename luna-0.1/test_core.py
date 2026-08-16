import asyncio

from brains.mock import MockProvider
from core.orchestrator import LunaCore
from core.registry import ProviderRegistry


async def main():
    registry = ProviderRegistry()

    registry.register(MockProvider())

    luna = LunaCore(
        registry.all()
    )

    response = await luna.ask(
        "Hello Luna",
        task="conversation",
    )

    print("Response:", response.text)
    print("Provider:", response.provider)
    print("Registered:", registry.names())


if __name__ == "__main__":
    asyncio.run(main())