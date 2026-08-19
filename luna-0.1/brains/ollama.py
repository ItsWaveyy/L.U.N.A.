import requests

from config import OLLAMA_BASE_URL
from core.providers import AIProvider, AIRequest, AIResponse


class OllamaProvider(AIProvider):
    """Local Ollama-powered AI provider for L.U.N.A."""

    name = "local"

    def __init__(self, model: str = "qwen3:1.7b"):
        self.model = model
        self.base_url = OLLAMA_BASE_URL.rstrip("/")

    @property
    def capabilities(self) -> set[str]:
        return {
            "general",
            "conversation",
            "fast",
        }

    async def generate(self, request: AIRequest) -> AIResponse:
        messages = [
            {
                "role": "system",
                "content": """
    You are L.U.N.A.'s local utility brain.

    You handle fast, simple tasks and short conversational requests.

    Be concise.
    Answer directly.
    Do not explain simple answers unless explanation is requested.
    Do not use emojis unless they are appropriate.
    Do not add unnecessary introductions or conclusions.
    """,
            }
        ]

        if request.system_prompt:
            messages.append({
                "role": "system",
                "content": request.system_prompt,
            })

        messages.append({
            "role": "user",
            "content": request.prompt,
        })

        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "stream": False,
            },
            timeout=120,
        )

        response.raise_for_status()

        data = response.json()

        return AIResponse(
            text=data["message"]["content"],
            provider=self.name,
            model=self.model,
        )

    async def health_check(self) -> bool:
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5,
            )

            return response.ok

        except Exception:
            return False