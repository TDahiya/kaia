"""Weather lookup via Google Weather API."""

import httpx
from app.config import get_settings
from app.services.tool_registry import ToolDef, registry

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
WEATHER_URL = "https://weather.googleapis.com/v1/currentConditions:lookup"


async def get_weather(city: str, **ctx) -> dict:
    key = get_settings().google_maps_api_key
    if not key:
        return {"error": "Google Maps API key not configured."}

    async with httpx.AsyncClient(timeout=10) as client:
        geo = await client.get(GEOCODE_URL, params={"address": city, "key": key})
        if geo.status_code != 200:
            return {"error": f"Geocoding failed: {geo.status_code}"}
        geo_data = geo.json()
        results = geo_data.get("results")
        if not results:
            return {"error": f"City not found: {city}"}

        loc = results[0]["geometry"]["location"]
        lat, lng = loc["lat"], loc["lng"]
        name = results[0].get("formatted_address", city)

        wx = await client.get(WEATHER_URL, params={
            "key": key,
            "location.latitude": lat,
            "location.longitude": lng,
            "unitsSystem": "METRIC",
        })
        if wx.status_code != 200:
            return {"error": f"Weather API error: {wx.status_code} — {wx.text[:200]}"}
        data = wx.json()

    current = data.get("currentConditions", data)
    return {
        "city": name,
        "temperature": current.get("temperature", {}).get("degrees"),
        "feels_like": current.get("feelsLikeTemperature", {}).get("degrees"),
        "humidity": current.get("relativeHumidity"),
        "description": current.get("weatherCondition", {}).get("description", {}).get("text", ""),
        "wind_speed_kmh": current.get("wind", {}).get("speed", {}).get("value"),
        "wind_direction": current.get("wind", {}).get("direction", {}).get("cardinal"),
        "uv_index": current.get("uvIndex"),
    }


registry.register(ToolDef(
    name="get_weather",
    description="Get current weather for a city using Google Weather API. Returns temperature, humidity, wind, and conditions.",
    input_schema={
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name, e.g. 'Dublin' or 'London'"},
        },
        "required": ["city"],
    },
    executor=get_weather,
    category="information",
))
