"""Phone tools — ONLY call the owner's number. Strict backend enforcement."""

import re
from datetime import date
from app.config import get_settings
from app.database import get_supabase
from app.services.tool_registry import ToolDef, registry
from app.services import app_settings

E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")


async def call_owner(reason: str = "", **ctx) -> dict:
    """Initiate a call to the owner's phone via Twilio."""
    s = get_settings()
    owner_number = app_settings.get_owner_phone()
    if not owner_number or not E164_RE.match(owner_number):
        return {"error": "Owner phone number not configured or invalid."}

    if not s.twilio_account_sid or not s.twilio_auth_token or not s.twilio_phone_number:
        return {"error": "Twilio not configured. Cannot make calls."}

    db = get_supabase()
    org_id = ctx.get("org_id", "")
    today = date.today().isoformat()
    existing = db.table("call_logs") \
        .select("id") \
        .eq("org_id", org_id) \
        .eq("direction", "outbound") \
        .gte("started_at", f"{today}T00:00:00Z") \
        .execute()
    if len(existing.data) >= s.daily_outbound_call_limit:
        return {"error": f"Daily outbound call limit reached ({s.daily_outbound_call_limit})."}

    from app.services.usage_tracker import check_spend_limit
    if not await check_spend_limit(org_id):
        return {"error": "Monthly spend limit reached. Cannot initiate calls."}

    import httpx
    host = s.app_base_url.replace("https://", "").replace("http://", "")
    twiml_url = f"{s.app_base_url}/api/telephony/webhook/voice"
    status_url = f"{s.app_base_url}/api/telephony/webhook/status"

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{s.twilio_account_sid}/Calls.json",
            auth=(s.twilio_account_sid, s.twilio_auth_token),
            data={
                "To": owner_number,
                "From": s.twilio_phone_number,
                "Url": twiml_url,
                "StatusCallback": status_url,
                "Timeout": 30,
                "TimeLimit": s.max_call_duration_seconds,
            },
        )
        if resp.status_code not in (200, 201):
            return {"error": f"Twilio API error: {resp.status_code} — {resp.text[:200]}"}
        call_data = resp.json()

    db.table("call_logs").insert({
        "org_id": org_id,
        "direction": "outbound",
        "caller_number": s.twilio_phone_number,
        "callee_number": owner_number,
        "status": "initiated",
        "telnyx_call_control_id": call_data.get("sid"),
        "metadata": {"reason": reason},
    }).execute()

    return {
        "success": True,
        "message": f"Calling owner at {owner_number}",
        "call_sid": call_data.get("sid"),
    }


registry.register(ToolDef(
    name="call_owner",
    description="Call the owner's personal phone number. This is the ONLY phone number the assistant can call. Requires explicit user instruction.",
    input_schema={
        "type": "object",
        "properties": {
            "reason": {"type": "string", "description": "Brief reason for the call"},
        },
        "required": [],
    },
    executor=call_owner,
    requires_confirmation=True,
    category="phone",
))
