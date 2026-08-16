from core.providers import AIProvider, AIRequest, AIResponse
from core.router import AIRouter


class LunaCore:
    """
    Central intelligence layer for L.U.N.A.

    Voice interfaces, apps, and devices should communicate
    with LunaCore rather than directly with an AI provider.
    """

    def __init__(self, providers: list[AIProvider]):
        self.router = AIRouter(providers)

    async def ask(
        self,
        prompt: str,
        task: str = "general",
        system_prompt: str | None = None,
    ) -> AIResponse:
        request = AIRequest(
            prompt=prompt,
            task=task,
            system_prompt=system_prompt,
        )

        return await self.router.generate(request)