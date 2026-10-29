"""Weather lookup via OpenWeatherMap (free tier)."""

import httpx
from app.config import get_settings
from app.services.tool_registry import ToolDef, registry

WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"


async def get_weather(city: str, units: str = "metric") -> dict:
    key = get_settings().openweather_api_key
    if not key:
        return {"error": "Weather API not configured"}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(WEATHER_URL, params={
            "q": city, "appid": key, "units": units,
        })
        if resp.status_code != 200:
            return {"error": f"Weather API error: {resp.status_code}"}
        data = resp.json()

    return {
        "city": data.get("name"),
        "country": data.get("sys", {}).get("country"),
        "temperature": data["main"]["temp"],
        "feels_like": data["main"]["feels_like"],
        "humidity": data["main"]["humidity"],
        "description": data["weather"][0]["description"] if data.get("weather") else "",
        "wind_speed": data.get("wind", {}).get("speed"),
        "units": units,
    }


registry.register(ToolDef(
    name="get_weather",
    description="Get current weather for a city. Returns temperature, humidity, wind, and conditions.",
    input_schema={
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name, e.g. 'Dublin' or 'Dublin,IE'"},
            "units": {"type": "string", "enum": ["metric", "imperial"], "default": "metric"},
        },
        "required": ["city"],
    },
    executor=get_weather,
    category="information",
))
