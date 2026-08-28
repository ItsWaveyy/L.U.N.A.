import asyncio
import logging

from livekit.agents import function_tool, RunContext
from langchain_community.tools import DuckDuckGoSearchRun


async def search_web_query(query: str) -> str:
    """Core-facing web search operation, independent of LiveKit."""

    try:
        results = await asyncio.to_thread(
            DuckDuckGoSearchRun().run,
            query,
        )
        logging.info("Web search completed for: %s", query)
        return results
    except Exception as exc:
        logging.error("Web search error: %s", exc)
        return "I couldn't complete the web search."


@function_tool()
async def search_web(
    context: RunContext,
    query: str,
) -> str:
    """
    Search the internet for information.
    """

    return await search_web_query(query)
