import json

import httpx

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
            "coding",
            "research",
            "creative",
            "fast",
        }

    async def generate(self, request: AIRequest) -> AIResponse:
        messages = [
            {
                "role": "system",
                "content": """
You are L.U.N.A.'s local utility brain.

You are running locally through Ollama.
You may be operating completely offline.

Handle fast, simple tasks and short conversational requests.

Be concise.
Answer directly.
Do not explain simple answers unless explanation is requested.
Do not invent current information when operating offline.
Do not claim to have internet access.
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

        chunks: list[str] = []

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=3.0,
                read=120.0,
                write=10.0,
                pool=5.0,
            )
        ) as client:

            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "think": False,
                    "keep_alive": "30m",
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 120,
                    },
                },
            ) as response:

                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    data = json.loads(line)

                    message = data.get("message", {})
                    content = message.get("content", "")

                    if content:
                        chunks.append(content)

                    if data.get("done"):
                        break

        return AIResponse(
            text="".join(chunks),
            provider=self.name,
            model=self.model,
            metadata={
                "offline_capable": True,
                "streamed": True,
            },
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(
                timeout=3.0
            ) as client:
                response = await client.get(
                    f"{self.base_url}/api/tags"
                )

            return response.is_success

        except Exception:
            return False