"""Google Calendar tools — list events, check availability, create/update/cancel events."""

from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from app.services.tool_registry import ToolDef, registry
from app.services.google_auth import get_google_credentials


async def _get_calendar_service(user_id: str, org_id: str):
    creds = await get_google_credentials(user_id, org_id)
    if not creds:
        raise ValueError("Google Calendar not connected. Please authorize Google in Settings.")
    return build("calendar", "v3", credentials=creds)


async def list_events(
    time_min: str = "", time_max: str = "", max_results: int = 10, **ctx
) -> dict:
    service = await _get_calendar_service(ctx["user_id"], ctx["org_id"])
    now = datetime.now(timezone.utc)
    if not time_min:
        time_min = now.isoformat()
    if not time_max:
        time_max = (now + timedelta(days=7)).isoformat()

    result = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events = []
    for e in result.get("items", []):
        start = e.get("start", {}).get("dateTime", e.get("start", {}).get("date", ""))
        end = e.get("end", {}).get("dateTime", e.get("end", {}).get("date", ""))
        events.append({
            "id": e["id"],
            "summary": e.get("summary", "(No title)"),
            "start": start,
            "end": end,
            "location": e.get("location"),
            "hangout_link": e.get("hangoutLink"),
            "html_link": e.get("htmlLink"),
            "attendees": [a.get("email") for a in e.get("attendees", [])],
        })
    return {"events": events, "count": len(events)}


async def check_availability(date: str, **ctx) -> dict:
    """Check free/busy for a given date (YYYY-MM-DD)."""
    service = await _get_calendar_service(ctx["user_id"], ctx["org_id"])
    day_start = f"{date}T00:00:00Z"
    day_end = f"{date}T23:59:59Z"

    body = {
        "timeMin": day_start,
        "timeMax": day_end,
        "items": [{"id": "primary"}],
    }
    result = service.freebusy().query(body=body).execute()
    busy = result.get("calendars", {}).get("primary", {}).get("busy", [])
    return {"date": date, "busy_slots": busy, "is_free": len(busy) == 0}


async def create_event(
    summary: str, start_time: str, end_time: str,
    description: str = "", location: str = "",
    attendee_email: str = "", timezone_str: str = "Europe/Dublin",
    **ctx,
) -> dict:
    service = await _get_calendar_service(ctx["user_id"], ctx["org_id"])
    event_body: dict = {
        "summary": summary,
        "start": {"dateTime": start_time, "timeZone": timezone_str},
        "end": {"dateTime": end_time, "timeZone": timezone_str},
    }
    if description:
        event_body["description"] = description
    if location:
        event_body["location"] = location
    if attendee_email:
        event_body["attendees"] = [{"email": attendee_email}]
        event_body["conferenceData"] = {
            "createRequest": {"requestId": f"kaia-{int(datetime.now().timestamp())}"}
        }

    created = service.events().insert(
        calendarId="primary",
        body=event_body,
        sendUpdates="all" if attendee_email else "none",
        conferenceDataVersion=1 if attendee_email else 0,
    ).execute()

    return {
        "success": True,
        "event_id": created["id"],
        "html_link": created.get("htmlLink"),
        "hangout_link": created.get("hangoutLink"),
        "start": created.get("start", {}).get("dateTime"),
        "end": created.get("end", {}).get("dateTime"),
    }


async def cancel_event(event_id: str, **ctx) -> dict:
    service = await _get_calendar_service(ctx["user_id"], ctx["org_id"])
    service.events().delete(
        calendarId="primary", eventId=event_id, sendUpdates="all"
    ).execute()
    return {"success": True, "cancelled_event_id": event_id}


for tool in [
    ToolDef(
        name="list_calendar_events",
        description="List upcoming calendar events. Returns event titles, times, attendees, and links.",
        input_schema={
            "type": "object",
            "properties": {
                "time_min": {"type": "string", "description": "Start of range (ISO 8601). Defaults to now."},
                "time_max": {"type": "string", "description": "End of range (ISO 8601). Defaults to 7 days from now."},
                "max_results": {"type": "integer", "default": 10},
            },
            "required": [],
        },
        executor=list_events,
        category="google",
    ),
    ToolDef(
        name="check_calendar_availability",
        description="Check if a specific date is free or busy.",
        input_schema={
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date to check (YYYY-MM-DD)"},
            },
            "required": ["date"],
        },
        executor=check_availability,
        category="google",
    ),
    ToolDef(
        name="create_calendar_event",
        description="Create a new calendar event with optional attendees and video conferencing.",
        input_schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Event title"},
                "start_time": {"type": "string", "description": "Start time (ISO 8601 with timezone)"},
                "end_time": {"type": "string", "description": "End time (ISO 8601 with timezone)"},
                "description": {"type": "string"},
                "location": {"type": "string"},
                "attendee_email": {"type": "string", "description": "Email of attendee to invite"},
                "timezone_str": {"type": "string", "default": "Europe/Dublin"},
            },
            "required": ["summary", "start_time", "end_time"],
        },
        executor=create_event,
        requires_confirmation=True,
        category="google",
    ),
    ToolDef(
        name="cancel_calendar_event",
        description="Cancel/delete a calendar event by its ID.",
        input_schema={
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "The event ID to cancel"},
            },
            "required": ["event_id"],
        },
        executor=cancel_event,
        requires_confirmation=True,
        category="google",
    ),
]:
    registry.register(tool)
