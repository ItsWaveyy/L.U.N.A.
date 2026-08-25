from core.providers.base import AIProvider, AIRequest, AIResponse

from livekit.plugins import google


class GeminiProvider(AIProvider):
    """
    Gemini-backed L.U.N.A. Core provider.

    This is the primary reasoning brain for L.U.N.A.
    """

    name = "gemini"

    def __init__(
        self,
        model: str = "gemini-3.1-flash-lite",
    ):
        self.model = model

        self.llm = google.LLM(
            model=self.model,
        )

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

    async def generate(
        self,
        request: AIRequest,
    ) -> AIResponse:

        raise NotImplementedError(
            "GeminiProvider.generate() is not connected to "
            "the Core execution layer yet."
        )

    async def health_check(self) -> bool:
        return True