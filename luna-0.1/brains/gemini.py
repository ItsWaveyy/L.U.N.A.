import httpx
from google import genai
from google.genai import types

from config import GOOGLE_API_KEY
from core.providers import AIProvider, AIRequest, AIResponse


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, model: str = "gemini-3.6-flash"):
        if not GOOGLE_API_KEY:
            raise RuntimeError("GOOGLE_API_KEY is not configured.")

        self.model = model

        self.http_client = httpx.AsyncClient()

        self.client = genai.Client(
            api_key=GOOGLE_API_KEY,
            http_options=types.HttpOptions(
                httpx_async_client=self.http_client,
            ),
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

    async def generate(self, request: AIRequest) -> AIResponse:
        prompt = request.prompt

        if request.system_prompt:
            prompt = (
                f"System instructions:\n"
                f"{request.system_prompt}\n\n"
                f"User request:\n"
                f"{request.prompt}"
            )

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
        )

        return AIResponse(
            text=response.text or "",
            provider=self.name,
            model=self.model,
        )

    async def health_check(self) -> bool:
        try:
            await self.client.aio.models.list()
            return True

        except Exception as exc:
            print(
                f"[L.U.N.A.] Gemini health check failed: {exc}"
            )
            return False

    async def close(self) -> None:
        await self.http_client.aclose()