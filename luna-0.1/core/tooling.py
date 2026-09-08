"""Core-owned tools and a provider-neutral tool-call protocol."""

import inspect
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


ToolHandler = Callable[..., Awaitable[str] | str]


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

        execution_arguments = dict(arguments)

        if tool.requires_explicit_request and not execution_arguments.pop(
            "explicit_request",
            False,
        ):
            return (
                f"Tool '{name}' requires an explicit user request before "
                "it can run."
            )

        try:
            result = tool.handler(**execution_arguments)

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

    from tools.canvas import get_canvas_calendar

    from tools.reminders import (
        create_reminder,
        list_active_reminders,
        cancel_reminder,
    )

    async def send_email(
        recipient: str,
        subject: str,
        body: str,
    ) -> str:
        from tools.email_tool import send_email_message

        return await send_email_message(
            recipient,
            subject,
            body,
        )

    async def inspect_self() -> str:
        """
        Perform a read-only inspection of L.U.N.A.'s repository.

        This tool cannot modify files, create plans, approve changes,
        execute changes, or run repository code.
        """

        from core.improvement.inspector import (
            RepositoryInspector,
        )

        from pathlib import Path

        repository_root = (
            Path(__file__).resolve().parent.parent
        )

        inspector = RepositoryInspector(
            repository_root
        )

        snapshot = inspector.inspect()

        return (
            f"L.U.N.A. repository inspection complete. "
            f"Python files: {len(snapshot.python_files)}. "
            f"Modules: {len(snapshot.modules)}. "
            f"Directories: {len(snapshot.directories)}."
        )

    return ToolRegistry([
        CoreTool(
            name="remember",
            description=(
                "Store a user-provided memory. "
                "Arguments: memory."
            ),
            handler=remember,
        ),
        CoreTool(
            name="recall",
            description=(
                "Search saved memories. "
                "Arguments: query."
            ),
            handler=recall,
        ),
        CoreTool(
            name="weather",
            description=(
                "Get weather or a forecast. "
                "Arguments: city, days (1-10)."
            ),
            handler=weather,
            requires_network=True,
        ),
        CoreTool(
            name="search_web",
            description=(
                "Search the web. "
                "Arguments: query."
            ),
            handler=search_web,
            requires_network=True,
        ),
        CoreTool(
            name="send_email",
            description=(
                "Send an email. "
                "Arguments: recipient, subject, body, "
                "explicit_request=true."
            ),
            handler=send_email,
            requires_network=True,
            requires_explicit_request=True,
        ),
        CoreTool(
            name="canvas_calendar",
            description=(
                "Read the user's Canvas calendar. Use this for questions "
                "about classes, assignments, due dates, exams, quizzes, "
                "schedule, or upcoming Canvas events. Summarize results "
                "naturally for the user. Do not expose raw Canvas course IDs, "
                "section numbers, CRNs, semester codes, teacher names, meeting "
                "times, or other internal Canvas metadata unless the user "
                "specifically asks for those details. For assignment questions, "
                "prioritize the assignment name, course subject, and due date. "
                "Arguments: scope ('today', 'tomorrow', 'week', or 'upcoming'), "
                "optional query text, and optional days for upcoming searches."
            ),
            handler=get_canvas_calendar,
            requires_network=True,
        ),
        CoreTool(
            name="create_reminder",
            description=(
                "Create a persistent reminder for the user. "
                "Use this when the user explicitly asks L.U.N.A. "
                "to remind them about something at a specific time. "
                "Arguments: message and remind_at. "
                "remind_at must be an ISO-8601 datetime with timezone."
            ),
            handler=create_reminder,
        ),
        CoreTool(
            name="list_active_reminders",
            description=(
                "List the user's active reminders, including reminders "
                "scheduled for the future. Use this when the user asks "
                "what reminders they have, what reminders are active, "
                "or what they are being reminded about. "
                "Do not invent reminder state."
            ),
            handler=list_active_reminders,
        ),
        CoreTool(
            name="cancel_reminder",
            description=(
                "Cancel an active reminder. Use this when the user explicitly "
                "asks to cancel, delete, remove, or stop a reminder. "
                "Arguments: reminder_id."
            ),
            handler=cancel_reminder,
            requires_explicit_request=True,
        ),
        CoreTool(
            name="inspect_self",
            description=(
                "Perform a read-only inspection of L.U.N.A.'s own repository. "
                "Use this when the user explicitly asks L.U.N.A. to inspect "
                "itself, review its structure, or analyze its current codebase. "
                "This tool cannot modify files or execute changes."
            ),
            handler=inspect_self,
        ),
    ])