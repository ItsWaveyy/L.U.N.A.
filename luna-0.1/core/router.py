from core.providers import AIProvider, AIRequest, AIResponse


class AIRouter:
    """Selects the best available AI provider and handles fallback."""

    TASK_PREFERENCES = {
        "coding": ["groq", "gemini", "local"],
        "research": ["gemini", "groq", "local"],
        "creative": ["gemini", "groq", "local"],
        "conversation": ["gemini", "groq", "local"],
        "fast": ["local", "groq", "gemini"],
        "general": ["gemini", "groq", "local"],
    }

    def __init__(self, providers: list[AIProvider]):
        self.providers = providers

    async def generate(
        self,
        request: AIRequest,
    ) -> AIResponse:
        candidates = self._rank_providers(request.task)

        if not candidates:
            raise RuntimeError(
                f"No providers available for task '{request.task}'."
            )

        attempted_providers = []
        last_error = None

        for index, provider in enumerate(candidates):
            attempted_providers.append(provider.name)

            try:
                if not await provider.health_check():
                    print(
                        f"[L.U.N.A.] Provider '{provider.name}' "
                        "is unhealthy. Trying fallback."
                    )
                    continue

                response = await provider.generate(request)

                response.metadata.update({
                    "task": request.task,
                    "routing": "task_preference",
                    "provider_attempts": len(attempted_providers),
                    "providers_tried": attempted_providers,
                })

                if index > 0:
                    response.metadata["fallback_used"] = True
                    response.metadata["fallback_from"] = candidates[0].name
                else:
                    response.metadata["fallback_used"] = False

                return response

            except Exception as exc:
                last_error = exc

                print(
                    f"[L.U.N.A.] Provider '{provider.name}' failed: {exc}"
                )

                if index < len(candidates) - 1:
                    next_provider = candidates[index + 1].name

                    print(
                        f"[L.U.N.A.] Falling back to "
                        f"'{next_provider}'."
                    )

        if last_error:
            raise RuntimeError(
                f"All providers failed for task "
                f"'{request.task}'. Tried: "
                f"{', '.join(attempted_providers)}"
            ) from last_error

        raise RuntimeError(
            f"No healthy providers available for task "
            f"'{request.task}'. Tried: "
            f"{', '.join(attempted_providers)}"
        )

    def _rank_providers(
        self,
        task: str,
    ) -> list[AIProvider]:
        preferences = self.TASK_PREFERENCES.get(
            task,
            self.TASK_PREFERENCES["general"],
        )

        available = {
            provider.name: provider
            for provider in self.providers
        }

        ranked = []

        for provider_name in preferences:
            provider = available.get(provider_name)

            if provider is None:
                continue

            if task not in provider.capabilities:
                continue

            ranked.append(provider)

        return ranked