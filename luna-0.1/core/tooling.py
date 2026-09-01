"""Core-owned tools and a provider-neutral tool-call protocol."""

import inspect
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


ToolHandler = Callable[..., Awaitable[str]]


@dataclass(frozen=True)
class CoreTool:
    name: str
    description: str
    handler: ToolHandler
    requires_network: bool = False
    requires_explicit_request: bool = False


class ToolRegistry:
    """The single tool boundary used by LunaCore."""

    def __init__(self, tools: list[CoreTool] | None = None):
        self._tools = {tool.name: tool for tool in tools or []}

    def get(self, name: str) -> CoreTool | None:
        return self._tools.get(name)

    def definitions(self) -> str:
        if not self._tools:
            return "No tools are available."

        return "\n".join(
            f"- {tool.name}: {tool.description}"
            for tool in self._tools.values()
        )

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        offline: bool,
    ) -> str:
        tool = self.get(name)

        if tool is None:
            return f"Tool '{name}' is not available."

        if offline and tool.requires_network:
            return f"Tool '{name}' requires a network connection."

        if tool.requires_explicit_request and not arguments.pop(
            "explicit_request",
            False,
        ):
            return (
                f"Tool '{name}' requires an explicit user request before "
                "it can run."
            )

        try:
            result = tool.handler(**arguments)

            if inspect.isawaitable(result):
                return str(await result)

            return str(result)

        except Exception as exc:
            return f"Tool '{name}' failed: {exc}"


def parse_tool_calls(text: str) -> list[tuple[str, dict[str, Any]]] | None:
    """Parse only a complete, provider-neutral tool-call response."""

    try:
        payload = json.loads(text.strip())
    except (json.JSONDecodeError, TypeError):
        return None

    calls = payload.get("tool_calls") if isinstance(payload, dict) else None

    if not isinstance(calls, list) or not calls:
        return None

    parsed = []

    for call in calls:
        if not isinstance(call, dict):
            return None

        name = call.get("name")
        arguments = call.get("arguments", {})

        if not isinstance(name, str) or not isinstance(arguments, dict):
            return None

        parsed.append((name, arguments))

    return parsed


def build_default_tool_registry() -> ToolRegistry:
    """Load tools lazily, keeping the Core independent of LiveKit wrappers."""

    async def remember(memory: str) -> str:
        from tools.memory import store_memory
        return await store_memory(memory)

    async def recall(query: str) -> str:
        from tools.memory import recall_memories
        return await recall_memories(query)

    async def weather(city: str, days: int = 1) -> str:
        from tools.weather import get_weather_for_city
        return await get_weather_for_city(city, days)

    async def search_web(query: str) -> str:
        from tools.web import search_web_query
        return await search_web_query(query)

    async def send_email(
        recipient: str,
        subject: str,
        body: str,
    ) -> str:
        from tools.email_tool import send_email_message
        return await send_email_message(recipient, subject, body)

    return ToolRegistry([
        CoreTool(
            name="remember",
            description="Store a user-provided memory. Arguments: memory.",
            handler=remember,
        ),
        CoreTool(
            name="recall",
            description="Search saved memories. Arguments: query.",
            handler=recall,
        ),
        CoreTool(
            name="weather",
            description="Get weather or a forecast. Arguments: city, days (1-10).",
            handler=weather,
            requires_network=True,
        ),
        CoreTool(
            name="search_web",
            description="Search the web. Arguments: query.",
            handler=search_web,
            requires_network=True,
        ),
        CoreTool(
            name="send_email",
            description=(
                "Send an email. Arguments: recipient, subject, body, "
                "explicit_request=true."
            ),
            handler=send_email,
            requires_network=True,
            requires_explicit_request=True,
        ),
    ])
