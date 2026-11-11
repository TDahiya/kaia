"""Twilio telephony webhooks — inbound/outbound call handling."""

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from app.config import get_settings
from app.database import get_supabase
from app.services import app_settings

router = APIRouter(prefix="/api/telephony", tags=["telephony"])


class OwnerPhoneUpdate(BaseModel):
    phone: str


@router.post("/webhook/voice")
async def twilio_voice_webhook(request: Request):
    """Handle inbound call — answer and stream audio to our WebSocket."""
    form = await request.form()
    call_sid = form.get("CallSid", "")
    from_number = form.get("From", "")
    to_number = form.get("To", "")
    direction = form.get("Direction", "inbound")

    s = get_settings()
    db = get_supabase()

    phone_result = db.table("phone_numbers") \
        .select("org_id") \
        .eq("phone_number", to_number) \
        .eq("status", "active") \
        .execute()
    org_id = phone_result.data[0]["org_id"] if phone_result.data else None

    if org_id:
        db.table("call_logs").insert({
            "org_id": org_id,
            "direction": "inbound",
            "caller_number": from_number,
            "callee_number": to_number,
            "status": "answered",
            "telnyx_call_control_id": call_sid,
        }).execute()

    host = s.app_base_url.replace("https://", "").replace("http://", "")
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://{host}/ws/call-media" />
    </Connect>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@router.post("/webhook/status")
async def twilio_status_webhook(request: Request):
    """Handle call status updates."""
    form = await request.form()
    call_sid = form.get("CallSid", "")
    call_status = form.get("CallStatus", "")
    duration = form.get("CallDuration")

    db = get_supabase()

    status_map = {
        "completed": "completed",
        "busy": "failed",
        "no-answer": "failed",
        "failed": "failed",
        "canceled": "failed",
    }
    mapped = status_map.get(call_status)
    if mapped:
        update = {"status": mapped}
        if duration:
            update["duration_seconds"] = int(duration)
        db.table("call_logs") \
            .update(update) \
            .eq("telnyx_call_control_id", call_sid) \
            .execute()

    return {"status": "ok"}


@router.post("/call-me")
async def call_me(request: Request):
    """Trigger Kaia to call the owner — used by the 'Call me' button in the UI."""
    s = get_settings()
    owner_phone = app_settings.get_owner_phone()
    if not owner_phone:
        return {"error": "No number set. Add yours in Settings."}
    if not s.twilio_account_sid:
        return {"error": "Twilio is not configured."}

    import httpx
    twiml_url = f"{s.app_base_url}/api/telephony/webhook/voice"
    status_url = f"{s.app_base_url}/api/telephony/webhook/status"

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{s.twilio_account_sid}/Calls.json",
            auth=(s.twilio_account_sid, s.twilio_auth_token),
            data={
                "To": owner_phone,
                "From": s.twilio_phone_number,
                "Url": twiml_url,
                "StatusCallback": status_url,
                "Timeout": 30,
            },
        )
        if resp.status_code not in (200, 201):
            return {"error": f"Call failed: {resp.text[:200]}"}
        call_data = resp.json()

    db = get_supabase()
    db.table("call_logs").insert({
        "org_id": "",
        "direction": "outbound",
        "caller_number": s.twilio_phone_number,
        "callee_number": owner_phone,
        "status": "initiated",
        "telnyx_call_control_id": call_data.get("sid"),
    }).execute()

    return {"success": True, "message": f"Calling {owner_phone}..."}


@router.get("/phone-numbers")
async def list_phone_numbers():
    db = get_supabase()
    result = db.table("phone_numbers").select("*").execute()
    s = get_settings()
    return {
        "phone_numbers": result.data,
        "configured_number": s.twilio_phone_number,
        "twilio_configured": bool(s.twilio_account_sid and s.twilio_auth_token),
    }


@router.get("/owner-phone")
async def get_owner_phone():
    """The single number Kaia is permitted to dial."""
    s = get_settings()
    return {
        "owner_phone": app_settings.get_owner_phone() or None,
        "from_number": s.twilio_phone_number or None,
        "twilio_configured": bool(s.twilio_account_sid and s.twilio_auth_token),
    }


@router.put("/owner-phone")
async def set_owner_phone(body: OwnerPhoneUpdate):
    try:
        phone = app_settings.normalize_phone(body.phone)
    except ValueError as e:
        raise HTTPException(400, str(e))

    app_settings.set_value(app_settings.OWNER_PHONE, phone)
    return {"success": True, "owner_phone": phone}
