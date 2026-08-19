from core.providers import AIProvider, AIRequest, AIResponse


class MockProvider(AIProvider):
    """Offline provider used for testing L.U.N.A.'s routing system."""

    name = "mock"

    @property
    def capabilities(self) -> set[str]:
        return {
            "general",
            "conversation",
            "coding",
            "research",
            "creative",
            "fast",
        }

    async def generate(self, request: AIRequest) -> AIResponse:
        return AIResponse(
            text=f"[MOCK] Received task: {request.prompt}",
            provider=self.name,
            model="mock",
        )

    async def health_check(self) -> bool:
        return True