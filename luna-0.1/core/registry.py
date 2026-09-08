from core.providers import AIProvider


class ProviderRegistry:
    """Stores and manages L.U.N.A.'s available AI providers."""

    def __init__(self):
        self._providers: dict[str, AIProvider] = {}

    def register(self, provider: AIProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> AIProvider | None:
        return self._providers.get(name)

    def all(self) -> list[AIProvider]:
        return list(self._providers.values())

    def names(self) -> list[str]:
        return list(self._providers.keys())