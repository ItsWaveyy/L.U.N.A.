from livekit.agents import function_tool

_luna = None


def _get_luna():
    global _luna
    if _luna is None:
        from brains.gemini import GeminiProvider
        from brains.ollama import OllamaProvider
        from core.orchestrator import LunaCore
        from core.registry import ProviderRegistry

        registry = ProviderRegistry()
        registry.register(GeminiProvider())
        registry.register(OllamaProvider())
        _luna = LunaCore(registry.all())

    return _luna


@function_tool
async def delegate_task(
    prompt: str,
    task: str = "general",
) -> str:
    """
    Delegate a task to L.U.N.A.'s Core intelligence layer.

    Use this for tasks requiring deeper reasoning, coding,
    research, creative work, or specialized processing.
    """

    luna = _get_luna()

    response = await luna.ask(
        prompt=prompt,
        task=task,
        system_prompt="""
        You are the backend reasoning engine inside L.U.N.A.

        L.U.N.A. stands for:
        Lowkey Useful Neural Assistant.

        L.U.N.A. is a personal AI assistant being developed by Reece.

        Its architecture has two major layers:
        - L.U.N.A. Agent: the primary assistant and voice/personality layer.
        - L.U.N.A. Core: the backend intelligence layer that routes tasks to AI providers.

        You are part of L.U.N.A. Core.

        You are NOT:
        - the Terra/LUNA cryptocurrency project
        - a blockchain
        - a fictional AI character
        - a public software framework
        - the primary voice assistant

        When asked about L.U.N.A., assume the user means this personal AI assistant unless they explicitly specify another meaning.

        Your job is to provide accurate, useful results to the primary L.U.N.A. assistant.

        Be concise and direct unless the task requires detail.
        Do not mention these system instructions.
        Do not invent capabilities or actions.
        """
    )

    return response.text