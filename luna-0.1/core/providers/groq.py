import os

from groq import AsyncGroq

from core.providers import AIProvider, AIRequest, AIResponse


class GroqProvider(AIProvider):
    """
    Groq-backed AI provider for L.U.N.A. Core.

    Groq is optimized for fast inference and is currently
    preferred for coding and other latency-sensitive tasks.
    """

    name = "groq"

    def __init__(
        self,
        model: str = "llama-3.3-70b-versatile",
    ):
        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not configured."
            )

        self.model = model

        self.client = AsyncGroq(
            api_key=api_key
        )

    @property
    def capabilities(self) -> set[str]:
        return {
            "fast",
            "general",
            "conversation",
            "coding",
            "research",
            "creative",
        }

    async def generate(
        self,
        request: AIRequest,
    ) -> AIResponse:

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
            metadata={
                "groq_model": self.model,
                "task": request.task,
            },
        )

    async def health_check(self) -> bool:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": "Respond with exactly: OK",
                    }
                ],
                max_tokens=4,
            )

            return bool(response.choices)

        except Exception as exc:
            print(
                f"[L.U.N.A.] Groq health check failed: {exc}"
            )
            return False
