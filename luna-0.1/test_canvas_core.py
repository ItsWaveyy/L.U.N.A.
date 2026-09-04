import asyncio

from core.tooling import build_default_tool_registry


async def main():
    registry = build_default_tool_registry()

    result = await registry.execute(
        "canvas_calendar",
        {
            "scope": "upcoming",
            "query": "Assignment",
            "days": 14,
        },
        offline=False,
    )

    print(result)


if __name__ == "__main__":
    asyncio.run(main())