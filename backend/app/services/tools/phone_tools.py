"""Phone tools — ONLY call the owner's number. Strict backend enforcement."""

import re
from datetime import date, timezone, datetime
from app.config import get_settings
from app.database import get_supabase
from app.services.tool_registry import ToolDef, registry

E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")


async def call_owner(reason: str = "", **ctx) -> dict:
    """Initiate a call to the owner's phone. Backend-enforced: only OWNER_PHONE_E164."""
    s = get_settings()
    owner_number = s.owner_phone_e164
    if not owner_number or not E164_RE.match(owner_number):
        return {"error": "Owner phone number not configured or invalid."}

    if not s.telnyx_api_key or not s.telnyx_connection_id:
        return {"error": "Telnyx not configured. Cannot make calls."}

    # Rate limit: daily outbound calls
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

    # Spend limit check
    from app.services.usage_tracker import check_spend_limit
    if not await check_spend_limit(org_id):
        return {"error": "Monthly spend limit reached. Cannot initiate calls."}

    # Initiate call via Telnyx
    import httpx
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://api.telnyx.com/v2/calls",
            headers={
                "Authorization": f"Bearer {s.telnyx_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "connection_id": s.telnyx_connection_id,
                "to": owner_number,
                "from": s.telnyx_phone_number,
                "timeout_secs": 30,
                "time_limit_secs": s.max_call_duration_seconds,
            },
        )
        if resp.status_code not in (200, 201):
            return {"error": f"Telnyx API error: {resp.status_code} — {resp.text[:200]}"}
        call_data = resp.json().get("data", {})

    # Log the call
    db.table("call_logs").insert({
        "org_id": org_id,
        "direction": "outbound",
        "caller_number": s.telnyx_phone_number,
        "callee_number": owner_number,
        "status": "initiated",
        "telnyx_call_control_id": call_data.get("call_control_id"),
        "metadata": {"reason": reason},
    }).execute()

    return {
        "success": True,
        "message": f"Calling owner at {owner_number}",
        "call_control_id": call_data.get("call_control_id"),
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
