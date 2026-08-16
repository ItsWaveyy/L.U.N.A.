import asyncio

from core.providers import AIRequest
from core.router import AIRouter
from brains.failing import FailingProvider
from brains.mock import MockProvider


async def main():
    router = AIRouter([
        FailingProvider(),
        MockProvider(),
    ])

    response = await router.generate(
        AIRequest(
            prompt="Hello Luna",
            task="conversation",
        )
    )

    print("Response:", response.text)
    print("Provider:", response.provider)


if __name__ == "__main__":
    asyncio.run(main())