from livekit.agents import function_tool

from brains.ollama import OllamaProvider
from core.orchestrator import LunaCore
from core.registry import ProviderRegistry


registry = ProviderRegistry()
registry.register(OllamaProvider())

luna = LunaCore(registry.all())


@function_tool
async def delegate_task(
    prompt: str,
    task: str = "general",
) -> str:
    """
    Delegate a task to L.U.N.A.'s core intelligence system.

    Use this when a request would benefit from deeper reasoning,
    coding, research, creative generation, or specialized AI processing.

    Args:
        prompt: The task that should be delegated.
        task: The category of the task. Options include general,
            conversation, coding, research, creative, and fast.
    """

    response = await luna.ask(
        prompt=prompt,
        task=task,
    )

    return response.text