"""Outbound mail for the guest portal.

Deliberately not a general send tool. Both functions below have a fixed
shape: the model supplies only the recipient (which must be the visitor's
own address) or the body of a message addressed to Tanishq. It can never
choose an arbitrary recipient and an arbitrary body at the same time, which
is what would turn this into a spam relay running on his Google account.
"""

import base64
import logging
from email.message import EmailMessage
from pathlib import Path

from app.config import get_settings
from app.database import get_supabase
from app.services.google_auth import get_google_credentials

logger = logging.getLogger(__name__)

CV_SUBJECT = "Tanishq Dahiya — CV"
CV_BODY = """Hi,

You asked Kaia for Tanishq's CV — it's attached.

Kaia is the assistant you were just talking to. He built it: voice, phone
calls, calendar and email actions, and spreadsheet analysis that runs real
code instead of guessing at numbers. The live version is at
https://kaia-ai.duckdns.org

If you'd like to speak to him directly, just reply to this email.

— Kaia (automated)
"""


async def _gmail_service():
    """Gmail client on the owner's account, or None."""
    db = get_supabase()
    row = db.table("integrations").select("user_id, org_id") \
        .eq("provider", "google").eq("status", "active").execute()
    if not row.data:
        return None
    creds = await get_google_credentials(row.data[0]["user_id"], row.data[0]["org_id"])
    if not creds:
        return None
    from googleapiclient.discovery import build
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


async def _send(msg: EmailMessage) -> tuple[bool, str]:
    try:
        svc = await _gmail_service()
    except Exception:
        logger.exception("guest mail: could not build Gmail client")
        return False, "Email isn't available right now."
    if svc is None:
        return False, "Email isn't connected right now — he'll have to send it himself."

    try:
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        svc.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True, ""
    except Exception:
        logger.exception("guest mail: send failed")
        return False, "That didn't go through. Try again, or ask him directly."


async def send_cv_email(to_addr: str, cv_path: Path) -> tuple[bool, str]:
    """Fixed subject, fixed body, one attachment, recipient supplied by the visitor."""
    msg = EmailMessage()
    msg["To"] = to_addr
    msg["Subject"] = CV_SUBJECT
    msg.set_content(CV_BODY)

    try:
        data = cv_path.read_bytes()
    except OSError:
        return False, "The CV file is missing."

    msg.add_attachment(
        data, maintype="application", subtype="pdf", filename=cv_path.name,
    )
    return await _send(msg)


async def send_relay(name: str, reply_to: str, body: str, via: str) -> tuple[bool, str]:
    """A message *to* Tanishq. Recipient is always him — never model-chosen."""
    s = get_settings()
    owner = (s.guest_relay_to or "").strip()
    if not owner:
        return False, "There's nowhere to deliver that right now."

    msg = EmailMessage()
    msg["To"] = owner
    msg["Subject"] = f"Kaia — message from {name}"
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(
        f"Someone used the guest portal and left you a message.\n\n"
        f"Name:  {name}\n"
        f"Email: {reply_to or '(not given)'}\n"
        f"Pass:  {via}\n"
        f"\n{'-' * 48}\n\n{body}\n"
    )
    return await _send(msg)
