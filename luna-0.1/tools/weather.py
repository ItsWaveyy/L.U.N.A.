import asyncio
import logging
import requests

from livekit.agents import function_tool, RunContext


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def _geocode_city(city: str) -> tuple[float, float, str]:
    """Convert a city name into latitude, longitude, and display name."""

    response = requests.get(
        GEOCODING_URL,
        params={
            "name": city,
            "count": 1,
            "language": "en",
            "format": "json",
        },
        timeout=10,
    )

    response.raise_for_status()

    payload = response.json()
    results = payload.get("results") or []

    if not results:
        raise ValueError(f"Location not found: {city}")

    location = results[0]

    latitude = location["latitude"]
    longitude = location["longitude"]

    display_name = location.get("name", city)

    admin1 = location.get("admin1")
    country = location.get("country")

    if admin1:
        display_name += f", {admin1}"

    if country:
        display_name += f", {country}"

    return latitude, longitude, display_name


def _get_forecast(
    latitude: float,
    longitude: float,
    days: int,
) -> dict:
    """Retrieve weather data from Open-Meteo."""

    response = requests.get(
        FORECAST_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": (
                "temperature_2m,"
                "apparent_temperature,"
                "weather_code,"
                "relative_humidity_2m,"
                "wind_speed_10m"
            ),
            "daily": (
                "weather_code,"
                "temperature_2m_max,"
                "temperature_2m_min,"
                "precipitation_probability_max"
            ),
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "timezone": "auto",
            "forecast_days": days,
        },
        timeout=10,
    )

    response.raise_for_status()

    return response.json()


def _weather_description(code: int | None) -> str:
    """Convert an Open-Meteo weather code into a readable description."""

    descriptions = {
        0: "clear sky",
        1: "mainly clear",
        2: "partly cloudy",
        3: "overcast",
        45: "fog",
        48: "depositing rime fog",
        51: "light drizzle",
        53: "moderate drizzle",
        55: "dense drizzle",
        56: "light freezing drizzle",
        57: "dense freezing drizzle",
        61: "slight rain",
        63: "moderate rain",
        65: "heavy rain",
        66: "light freezing rain",
        67: "heavy freezing rain",
        71: "slight snow",
        73: "moderate snow",
        75: "heavy snow",
        77: "snow grains",
        80: "slight rain showers",
        81: "moderate rain showers",
        82: "violent rain showers",
        85: "slight snow showers",
        86: "heavy snow showers",
        95: "thunderstorm",
        96: "thunderstorm with slight hail",
        99: "thunderstorm with heavy hail",
    }

    return descriptions.get(code, "unknown conditions")


def _format_current_weather(
    payload: dict,
    city: str,
) -> str:
    """Format current weather conditions."""

    current = payload.get("current") or {}

    temperature = current.get("temperature_2m")
    apparent = current.get("apparent_temperature")
    weather_code = current.get("weather_code")
    humidity = current.get("relative_humidity_2m")
    wind = current.get("wind_speed_10m")

    description = _weather_description(weather_code)

    parts = [
        f"Current weather in {city}:",
    ]

    if temperature is not None:
        parts.append(f"{temperature:.0f}°F")

    if apparent is not None:
        parts.append(f"feels like {apparent:.0f}°F")

    parts.append(description)

    if humidity is not None:
        parts.append(f"humidity {humidity}%")

    if wind is not None:
        parts.append(f"wind {wind:.0f} mph")

    return ", ".join(parts)


def _format_forecast(
    payload: dict,
    city: str,
    days: int,
) -> str:
    """Format a multi-day forecast."""

    daily = payload.get("daily") or {}

    dates = daily.get("time") or []
    max_temps = daily.get("temperature_2m_max") or []
    min_temps = daily.get("temperature_2m_min") or []
    weather_codes = daily.get("weather_code") or []
    precipitation = (
        daily.get("precipitation_probability_max") or []
    )

    if not dates:
        return f"I couldn't retrieve the forecast for {city}."

    lines = [
        f"{len(dates)}-day forecast for {city}:"
    ]

    for index, date in enumerate(dates):
        high = (
            max_temps[index]
            if index < len(max_temps)
            else None
        )

        low = (
            min_temps[index]
            if index < len(min_temps)
            else None
        )

        code = (
            weather_codes[index]
            if index < len(weather_codes)
            else None
        )

        rain = (
            precipitation[index]
            if index < len(precipitation)
            else None
        )

        description = _weather_description(code)

        line = f"{date}:"

        if high is not None:
            line += f" high {high:.0f}°F"

        if low is not None:
            line += f", low {low:.0f}°F"

        line += f", {description}"

        if rain is not None:
            line += f", {rain}% precipitation chance"

        lines.append(line)

    return "\n".join(lines)


async def get_weather_for_city(
    city: str,
    days: int = 1,
) -> str:
    """Core-facing weather operation, independent of LiveKit."""

    try:
        days = max(1, min(int(days), 10))
        latitude, longitude, display_name = await asyncio.to_thread(
            _geocode_city,
            city,
        )
        payload = await asyncio.to_thread(
            _get_forecast,
            latitude,
            longitude,
            days,
        )

        if days == 1:
            return _format_current_weather(payload, display_name)

        return _format_forecast(payload, display_name, days)

    except Exception as exc:
        logging.error("[L.U.N.A.] Weather error: %s", exc)
        return f"I couldn't retrieve the weather for {city}."


@function_tool()
async def get_weather(
    context: RunContext,
    city: str,
    days: int = 1,
) -> str:
    """
    Get current weather or a short forecast.

    Args:
        city: The city to check.
        days: Number of days to retrieve. Use 1 for current conditions.
    """

    return await get_weather_for_city(city, days)
