"""Placing the outbound call to a guest.

The pass id rides on the TwiML URL so the media handler knows this is a
guest call and swaps in the restricted prompt and tool set. Without that a
visitor on the phone would reach the owner's tools.
"""

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# Hard ceiling enforced by Twilio itself, not by the prompt.
MAX_CALL_SECONDS = 150
RING_TIMEOUT = 25


async def place_guest_call(number: str, pass_row: dict) -> tuple[bool, str]:
    s = get_settings()
    if not s.twilio_account_sid or not s.twilio_phone_number:
        return False, "Calling isn't configured right now."

    base = s.app_base_url.rstrip("/")
    twiml_url = f"{base}/api/telephony/webhook/voice?guest={pass_row['id']}"
    status_url = f"{base}/api/telephony/webhook/status"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{s.twilio_account_sid}/Calls.json",
                auth=(s.twilio_account_sid, s.twilio_auth_token),
                data={
                    "To": number,
                    "From": s.twilio_phone_number,
                    "Url": twiml_url,
                    "StatusCallback": status_url,
                    "Timeout": RING_TIMEOUT,
                    # Twilio drops the call at this point regardless of what
                    # the model is doing.
                    "TimeLimit": MAX_CALL_SECONDS,
                    "MachineDetection": "Enable",
                    "MachineDetectionTimeout": 10,
                },
            )
    except Exception:
        logger.exception("guest call: request failed")
        return False, "I couldn't start the call. Try again in a moment."

    if r.status_code not in (200, 201):
        logger.warning("guest call: twilio %s — %s", r.status_code, r.text[:300])
        return False, "The call didn't go through. Try again, or email him instead."

    logger.info("guest call: dialling for pass %s", pass_row["label"])
    return True, ""
