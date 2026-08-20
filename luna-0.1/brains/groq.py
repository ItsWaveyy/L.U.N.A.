from groq import AsyncGroq

from config import GROQ_API_KEY
from core.providers import AIProvider, AIRequest, AIResponse


class GroqProvider(AIProvider):
    name = "groq"

    def __init__(self, model: str = "openai/gpt-oss-120b"):
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not configured.")

        self.model = model
        self.client = AsyncGroq(api_key=GROQ_API_KEY)

    @property
    def capabilities(self) -> set[str]:
        return {
            "general",
            "coding",
            "research",
            "creative",
            "fast",
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
            temperature=0.7,
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

        except Exception as exc:
            print(
                f"[L.U.N.A.] Groq health check failed: {exc}"
            )
            return False