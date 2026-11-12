"""Twilio telephony webhooks — inbound/outbound call handling."""

import logging

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)
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
    answered_by = (form.get("AnsweredBy") or "").lower()

    s = get_settings()
    db = get_supabase()

    # Voicemail answers like a person and then reads its own prompts at you.
    # Without this Kaia holds a full conversation with the IVR, burning a
    # model call and TTS on every prompt until the mailbox hangs up.
    if answered_by.startswith("machine") or answered_by == "fax":
        logger.info("call-media: %s answered by %s — hanging up", call_sid, answered_by)
        if call_sid:
            try:
                db.table("call_logs").update({"status": "voicemail"}) \
                    .eq("telnyx_call_control_id", call_sid).execute()
            except Exception:
                pass
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response><Hangup/></Response>',
            media_type="application/xml",
        )

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

    # A guest call carries its pass id through to the media socket, which
    # uses it to swap in the restricted prompt and tool set.
    guest = (request.query_params.get("guest") or "").strip()
    stream = f"wss://{host}/ws/call-media"
    if guest:
        stream += f"?guest={guest}"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{stream}" />
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
                # Twilio decides human vs machine before running our TwiML,
                # so the webhook can hang up on voicemail instead of talking
                # to it. Synchronous (no AsyncAmd) so AnsweredBy is present.
                "MachineDetection": "Enable",
                "MachineDetectionTimeout": 10,
            },
        )
        if resp.status_code not in (200, 201):
            return {"error": f"Call failed: {resp.text[:200]}"}
        call_data = resp.json()

    # The call is already placed by this point. Logging it is bookkeeping,
    # so a failure here must not be reported to the user as a failed call —
    # an empty org_id used to throw here and surface as a 500 while the
    # phone was actively ringing.
    try:
        db = get_supabase()
        owner = db.table("users").select("org_id").limit(1).execute()
        org_id = owner.data[0]["org_id"] if owner.data else None
        if org_id:
            db.table("call_logs").insert({
                "org_id": org_id,
                "direction": "outbound",
                "caller_number": s.twilio_phone_number,
                "callee_number": owner_phone,
                "status": "initiated",
                "telnyx_call_control_id": call_data.get("sid"),
            }).execute()
    except Exception:
        logger.exception("call-me: placed the call but could not log it")

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
