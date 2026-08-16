import os

from openai import AsyncOpenAI

from core.providers import AIProvider, AIRequest, AIResponse


class OpenAIProvider(AIProvider):
    """OpenAI-backed AI provider for L.U.N.A."""

    name = "openai"

    def __init__(self, model: str = "gpt-5-mini"):
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured."
            )

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    @property
    def capabilities(self) -> set[str]:
        return {
            "general",
            "conversation",
            "coding",
            "research",
            "creative",
        }

    async def generate(self, request: AIRequest) -> AIResponse:
        messages = []

        if request.system_prompt:
            messages.append({
                "role": "system",
                "content": request.system_prompt,
            })

        messages.append({
            "role": "user",
            "content": request.prompt,
        })

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )

        text = response.choices[0].message.content or ""

        return AIResponse(
            text=text,
            provider=self.name,
            model=self.model,
        )

    async def health_check(self) -> bool:
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False