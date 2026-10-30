"""Google Maps tools — directions, place search, navigation links."""

import httpx
from urllib.parse import quote_plus
from app.config import get_settings
from app.services.tool_registry import ToolDef, registry

DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"
PLACES_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"


async def get_directions(destination: str, origin: str = "", travel_mode: str = "driving", **ctx) -> dict:
    """Get directions with ETA via Google Directions API + navigation link."""
    mode = travel_mode.lower()
    if mode not in ("driving", "walking", "bicycling", "transit"):
        mode = "driving"

    nav_params = f"api=1&destination={quote_plus(destination)}&travelmode={mode}"
    if origin:
        nav_params += f"&origin={quote_plus(origin)}"
    nav_url = f"https://www.google.com/maps/dir/?{nav_params}"

    key = get_settings().google_maps_api_key
    eta = None
    distance = None
    if key and origin:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(DIRECTIONS_URL, params={
                "origin": origin, "destination": destination,
                "mode": mode, "key": key,
            })
            if resp.status_code == 200:
                routes = resp.json().get("routes", [])
                if routes:
                    leg = routes[0].get("legs", [{}])[0]
                    eta = leg.get("duration", {}).get("text")
                    distance = leg.get("distance", {}).get("text")

    result = {
        "navigation_url": nav_url,
        "destination": destination,
        "origin": origin or "your current location",
        "travel_mode": mode,
    }
    if eta:
        result["estimated_time"] = eta
        result["distance"] = distance
    return result


async def search_places(query: str, **ctx) -> dict:
    """Search for places via Google Places API."""
    key = get_settings().google_maps_api_key
    maps_url = f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"

    if not key:
        return {"maps_url": maps_url, "query": query}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(PLACES_URL, params={"query": query, "key": key})
        if resp.status_code != 200:
            return {"maps_url": maps_url, "query": query}
        places = resp.json().get("results", [])[:5]

    return {
        "maps_url": maps_url,
        "query": query,
        "results": [
            {
                "name": p.get("name"),
                "address": p.get("formatted_address"),
                "rating": p.get("rating"),
                "open_now": p.get("opening_hours", {}).get("open_now"),
            }
            for p in places
        ],
    }


for tool in [
    ToolDef(
        name="get_directions",
        description="Get a Google Maps navigation link with directions from origin to destination. Returns a clickable link that opens turn-by-turn navigation.",
        input_schema={
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "Where to go, e.g. 'Dublin Airport' or '123 Main St, Dublin'"},
                "origin": {"type": "string", "description": "Starting point. Leave empty to use current location."},
                "travel_mode": {"type": "string", "enum": ["driving", "walking", "bicycling", "transit"], "default": "driving"},
            },
            "required": ["destination"],
        },
        executor=get_directions,
        category="maps",
    ),
    ToolDef(
        name="search_places",
        description="Search for a place, restaurant, shop, or business on Google Maps. Returns a clickable link to see it on the map.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for, e.g. 'coffee shops near DCU' or 'Tesco Dublin'"},
            },
            "required": ["query"],
        },
        executor=search_places,
        category="maps",
    ),
]:
    registry.register(tool)
