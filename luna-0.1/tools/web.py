import logging

from livekit.agents import function_tool, RunContext
from langchain_community.tools import DuckDuckGoSearchRun


@function_tool()
async def search_web(
    context: RunContext,
    query: str,
) -> str:
    """
    Search the internet for information.
    """

    try:
        search = DuckDuckGoSearchRun()

        results = search.run(query)

        logging.info(
            f"Web search completed for: {query}"
        )

        return results

    except Exception as e:
        logging.error(
            f"Web search error: {e}"
        )

        return "I couldn't complete the web search."