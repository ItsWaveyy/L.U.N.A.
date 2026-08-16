from core.providers import AIProvider, AIRequest, AIResponse


class AIRouter:
    """Selects the best available AI provider for a task."""

    # Preferred provider order for each task.
    # Providers not listed here can still be used through fallback.
    TASK_PREFERENCES = {
        "coding": ["anthropic", "openai", "gemini", "local"],
        "research": ["openai", "anthropic", "gemini", "local"],
        "creative": ["anthropic", "openai", "gemini", "local"],
        "conversation": ["gemini", "openai", "anthropic", "local"],
        "fast": ["local", "gemini", "openai", "anthropic"],
        "general": ["openai", "gemini", "anthropic", "local"],
    }

    def __init__(self, providers: list[AIProvider]):
        self.providers = providers

    async def generate(self, request: AIRequest) -> AIResponse:
        candidates = self._rank_providers(request.task)

        if not candidates:
            raise RuntimeError(
                f"No providers available for task '{request.task}'."
            )

        last_error = None

        for provider in candidates:
            try:
                if not await provider.health_check():
                    print(
                        f"[L.U.N.A.] Provider '{provider.name}' "
                        "is unhealthy. Skipping."
                    )
                    continue

                response = await provider.generate(request)

                response.metadata.update({
                    "task": request.task,
                    "routing": "task_preference",
                })

                return response

            except Exception as exc:
                last_error = exc
                print(
                    f"[L.U.N.A.] Provider '{provider.name}' failed: {exc}"
                )

        if last_error:
            raise RuntimeError(
                f"All providers failed for task '{request.task}'."
            ) from last_error

        raise RuntimeError(
            f"No healthy providers available for task '{request.task}'."
        )

    def _rank_providers(self, task: str) -> list[AIProvider]:
        """Return providers ordered according to task preference."""

        preferences = self.TASK_PREFERENCES.get(
            task,
            self.TASK_PREFERENCES["general"],
        )

        available = {
            provider.name: provider
            for provider in self.providers
        }

        ranked = []

        # Add providers in preferred order.
        for provider_name in preferences:
            provider = available.get(provider_name)

            if provider is not None:
                ranked.append(provider)

        # Add any remaining providers as final fallbacks.
        for provider in self.providers:
            if provider not in ranked:
                ranked.append(provider)

        return ranked