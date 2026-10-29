"""Telnyx telephony webhooks — inbound/outbound call handling."""

import json
import hashlib
import hmac
from fastapi import APIRouter, Request, HTTPException
from app.config import get_settings
from app.database import get_supabase

router = APIRouter(prefix="/api/telephony", tags=["telephony"])


def verify_telnyx_webhook(request_body: bytes, signature: str, timestamp: str) -> bool:
    """Verify Telnyx webhook signature."""
    secret = get_settings().telnyx_webhook_secret
    if not secret:
        return True  # Skip verification if no secret configured (dev only)
    payload = f"{timestamp}|{request_body.decode()}"
    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhook")
async def telnyx_webhook(request: Request):
    body = await request.body()
    sig = request.headers.get("telnyx-signature-ed25519", "")
    ts = request.headers.get("telnyx-timestamp", "")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON")

    data = payload.get("data", {})
    event_type = data.get("event_type", "")
    call_payload = data.get("payload", {})
    call_control_id = call_payload.get("call_control_id", "")

    db = get_supabase()

    if event_type == "call.initiated":
        direction = call_payload.get("direction", "inbound")
        from_number = call_payload.get("from", "")
        to_number = call_payload.get("to", "")

        # For inbound calls, answer and start streaming
        if direction == "inbound":
            s = get_settings()
            # Find the phone number's org
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
                    "status": "ringing",
                    "telnyx_call_control_id": call_control_id,
                }).execute()

                # Answer the call
                import httpx
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(
                        f"https://api.telnyx.com/v2/calls/{call_control_id}/actions/answer",
                        headers={"Authorization": f"Bearer {s.telnyx_api_key}"},
                        json={},
                    )

    elif event_type == "call.answered":
        db.table("call_logs") \
            .update({"status": "answered"}) \
            .eq("telnyx_call_control_id", call_control_id) \
            .execute()

        # Start media streaming for AI interaction
        s = get_settings()
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telnyx.com/v2/calls/{call_control_id}/actions/streaming_start",
                headers={"Authorization": f"Bearer {s.telnyx_api_key}"},
                json={
                    "stream_url": f"wss://{s.app_base_url.replace('https://', '').replace('http://', '')}/ws/call-media",
                    "stream_track": "both_tracks",
                },
            )

    elif event_type == "call.hangup":
        db.table("call_logs") \
            .update({
                "status": "completed",
                "ended_at": call_payload.get("end_time"),
                "duration_seconds": call_payload.get("duration_seconds"),
            }) \
            .eq("telnyx_call_control_id", call_control_id) \
            .execute()

    elif event_type == "call.machine.detection.ended":
        pass  # handle voicemail detection if needed

    return {"status": "ok"}


@router.get("/phone-numbers")
async def list_phone_numbers():
    db = get_supabase()
    result = db.table("phone_numbers").select("*").execute()
    s = get_settings()
    return {
        "phone_numbers": result.data,
        "configured_number": s.telnyx_phone_number,
        "telnyx_configured": bool(s.telnyx_api_key),
    }
