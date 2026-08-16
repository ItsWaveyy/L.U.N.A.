from .providers import AIProvider, AIRequest, AIResponse


class AIRouter:
    """Selects the best available AI provider for a task."""

    def __init__(self, providers: list[AIProvider]):
        self.providers = providers

    async def generate(self, request: AIRequest) -> AIResponse:
        candidates = self._rank_providers(request.task)

        last_error = None

        for provider in candidates:
            try:
                if not await provider.health_check():
                    continue

                response = await provider.generate(request)
                return response

            except Exception as exc:
                last_error = exc
                print(
                    f"[L.U.N.A.] Provider '{provider.name}' failed: {exc}"
                )

        if last_error:
            raise RuntimeError(
                "All available AI providers failed."
            ) from last_error

        raise RuntimeError(
            "No available AI providers can handle this request."
        )

    def _rank_providers(self, task: str) -> list[AIProvider]:
        capable = [
            provider
            for provider in self.providers
            if task in provider.capabilities or "general" in provider.capabilities
        ]

        return capable