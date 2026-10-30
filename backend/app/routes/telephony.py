"""Twilio telephony webhooks — inbound/outbound call handling."""

from fastapi import APIRouter, Request, Form
from fastapi.responses import Response
from app.config import get_settings
from app.database import get_supabase

router = APIRouter(prefix="/api/telephony", tags=["telephony"])


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
