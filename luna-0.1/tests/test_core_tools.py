import asyncio

from brains.mock import MockProvider
from core.orchestrator import LunaCore
from core.router import AIRouter
from core.tooling import CoreTool, ToolRegistry
from core.providers import AIRequest, AIResponse


class ToolCallingProvider(MockProvider):
    def __init__(self):
        self.requests = []

    async def generate(self, request: AIRequest) -> AIResponse:
        self.requests.append(request)

        if len(self.requests) == 1:
            return AIResponse(
                text=(
                    '{"tool_calls":[{"name":"remember",'
                    '"arguments":{"memory":"prefers tea"}}]}'
                ),
                provider=self.name,
                model="tool-test",
            )

        return AIResponse(
            text="I'll remember that you prefer tea.",
            provider=self.name,
            model="tool-test",
        )


class MockOnlyRouter(AIRouter):
    TASK_PREFERENCES = {
        task: ["mock"]
        for task in ("fast", "general", "conversation", "coding", "research", "creative")
    }


def test_core_executes_tool_then_routes_final_answer():
    asyncio.run(_test_core_executes_tool_then_routes_final_answer())


async def _test_core_executes_tool_then_routes_final_answer():
    saved = []

    async def remember(memory: str) -> str:
        saved.append(memory)
        return f"Saved: {memory}"

    provider = ToolCallingProvider()
    core = LunaCore(
        providers=[provider],
        tools=ToolRegistry([
            CoreTool(
                name="remember",
                description="Store memory. Arguments: memory.",
                handler=remember,
            )
        ]),
    )
    core.router = MockOnlyRouter([provider])

    response = await core.ask("Remember that I prefer tea.")

    assert saved == ["prefers tea"]
    assert response.text == "I'll remember that you prefer tea."
    assert response.metadata["tools_used"] == ["remember"]
    assert len(provider.requests) == 2
    assert "Tool results" in provider.requests[1].prompt
