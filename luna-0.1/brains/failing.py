from core.providers import AIProvider, AIRequest, AIResponse


class FailingProvider(AIProvider):
    """Provider used to test L.U.N.A.'s fallback behavior."""

    name = "failing"

    @property
    def capabilities(self) -> set[str]:
        return {"general"}

    async def generate(self, request: AIRequest) -> AIResponse:
        raise RuntimeError("Simulated provider outage.")

    async def health_check(self) -> bool:
        return True