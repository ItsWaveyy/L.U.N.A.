import logging
import requests

from livekit.agents import function_tool, RunContext


@function_tool()
async def get_weather(
    context: RunContext,
    city: str,
) -> str:
    """
    Get the current weather for a city.
    """

    try:
        response = requests.get(
            f"https://wttr.in/{city}?format=3",
            timeout=10,
        )

        if response.status_code == 200:
            return response.text

        return f"I couldn't retrieve the weather for {city}."

    except Exception as e:
        logging.error(f"Weather error: {e}")
        return f"I couldn't retrieve the weather for {city}."