import logging
import requests

from livekit.agents import function_tool, RunContext


def _format_current_weather(payload: dict, city: str) -> str:
    try:
        current = (payload.get("current_condition") or [{}])[0]
        temp = current.get("temp_C")
        feels_like = current.get("FeelsLikeC")
        desc = ((current.get("weatherDesc") or [{}])[0].get("value"))
        humidity = current.get("humidity")
        wind = current.get("windspeedKmph")

        parts = [f"Current weather in {city}:"]
        if temp is not None:
            parts.append(f"{temp}°C")
        if feels_like is not None:
            parts.append(f"feels like {feels_like}°C")
        if desc:
            parts.append(desc)
        if humidity is not None:
            parts.append(f"humidity {humidity}%")
        if wind is not None:
            parts.append(f"wind {wind} km/h")

        return ", ".join(parts)
    except Exception:
        return f"I couldn't retrieve the weather for {city}."


def _format_forecast(payload: dict, city: str, days: int) -> str:
    try:
        weather = payload.get("weather") or []
        forecast = weather[: max(1, min(days, 10))]

        if not forecast:
            return f"I couldn't retrieve the forecast for {city}."

        lines = [f"{days}-day forecast for {city}:"]
        for day in forecast:
            date = day.get("date", "")
            maxtemp = day.get("maxtempC")
            mintemp = day.get("mintempC")
            desc = ((day.get("hourly") or [{}])[0].get("weatherDesc") or [{}])[0].get("value")
            line = f"{date}: high {maxtemp}°C, low {mintemp}°C"
            if desc:
                line += f", {desc}"
            lines.append(line)

        return "\n".join(lines)
    except Exception:
        return f"I couldn't retrieve the forecast for {city}."


@function_tool()
async def get_weather(
    context: RunContext,
    city: str,
    days: int = 1,
) -> str:
    """
    Get the current weather for a city or a short forecast.

    Args:
        city: The city to check.
        days: Number of forecast days to retrieve. Default is 1, which returns current conditions.
    """

    try:
        days = max(1, min(int(days), 10))
        response = requests.get(
            f"https://wttr.in/{city}?format=j1&days={days}",
            timeout=10,
        )

        if response.status_code != 200:
            return f"I couldn't retrieve the weather for {city}."

        payload = response.json()

        if days == 1:
            return _format_current_weather(payload, city)

        return _format_forecast(payload, city, days)

    except Exception as e:
        logging.error(f"Weather error: {e}")
        return f"I couldn't retrieve the weather for {city}."