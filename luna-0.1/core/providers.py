from dataclasses import dataclass, field
from typing import Any


@dataclass
class AIRequest:
    prompt: str
    task: str = "general"
    system_prompt: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AIResponse:
    text: str
    provider: str
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AIProvider:
    """Base interface for every AI brain L.U.N.A. can use."""

    name = "unknown"

    async def generate(self, request: AIRequest) -> AIResponse:
        raise NotImplementedError

    async def health_check(self) -> bool:
        return True

    @property
    def capabilities(self) -> set[str]:
        return {"general"}