import asyncio

from brains.failing import FailingProvider
from brains.mock import MockProvider
from core.orchestrator import LunaCore


async def main():
    luna = LunaCore([
        MockProvider(),
        FailingProvider(),
    ])

    status = await luna.health_status()

    print("--- PROVIDER HEALTH TEST ---")

    for provider, healthy in status.items():
        state = "ONLINE" if healthy else "OFFLINE"
        print(f"{provider}: {state}")

    assert status["mock"] is True
    assert status["failing"] is True

    print("\n--- HEALTH FAILURE TEST ---")

    class BrokenProvider(FailingProvider):
        async def health_check(self) -> bool:
            return False

    luna = LunaCore([
        MockProvider(),
        BrokenProvider(),
    ])

    status = await luna.health_status()

    print(f"mock: {'ONLINE' if status['mock'] else 'OFFLINE'}")
    print(
        f"broken: "
        f"{'ONLINE' if status['failing'] else 'OFFLINE'}"
    )

    assert status["mock"] is True
    assert status["failing"] is False

    print("\n✅ PROVIDER HEALTH TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
