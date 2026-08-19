import asyncio

from brains.failing import FailingProvider
from brains.mock import MockProvider
from core.router import AIRouter
from core.providers import AIRequest


class FallbackTestRouter(AIRouter):
    TASK_PREFERENCES = {
        "general": ["failing", "mock"],
    }


async def main():
    router = FallbackTestRouter([
        FailingProvider(),
        MockProvider(),
    ])

    request = AIRequest(
        prompt="Test whether L.U.N.A. can recover from a provider failure.",
        task="general",
    )

    response = await router.generate(request)

    print("\n--- FALLBACK TEST ---")
    print(f"Provider: {response.provider}")
    print(f"Model: {response.model}")
    print(f"Response: {response.text}")
    print(f"Fallback used: {response.metadata['fallback_used']}")
    print(f"Providers tried: {response.metadata['providers_tried']}")
    print(f"Provider attempts: {response.metadata['provider_attempts']}")

    assert response.provider == "mock"
    assert response.metadata["fallback_used"] is True
    assert response.metadata["providers_tried"] == [
        "failing",
        "mock",
    ]
    assert response.metadata["provider_attempts"] == 2

    print("\n✅ FALLBACK TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
