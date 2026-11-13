"""Issue, validate and meter guest access codes.

Codes are handed out one per person so usage is attributable and a single
code can be revoked. Every limit is enforced here rather than in a prompt,
because a prompt is the first thing a visitor will attack.
"""

import hmac
import json
import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.database import get_supabase

# No 0/O/1/I — these get read aloud and typed in from a message.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

SESSION_TTL_HOURS = 24

# Ceiling across all passes, so a leaked code cannot run up the bill.
# A callback is ~$0.18; text is ~$0.004.
DAILY_CALL_CEILING = 5
DAILY_MESSAGE_CEILING = 400


def make_code(label: str) -> str:
    """AMZN-4K2P: a short prefix from the label, then random."""
    prefix = "".join(c for c in (label or "").upper() if c.isalnum())[:4] or "KAIA"
    body = "".join(secrets.choice(ALPHABET) for _ in range(4))
    return f"{prefix}-{body}"


def create_pass(
    label: str,
    days: int = 1,
    max_messages: int = 20,
    max_calls: int = 1,
    note: str = "",
    org_id: str | None = None,
) -> dict:
    code = make_code(label)
    expires = datetime.now(timezone.utc) + timedelta(days=max(1, min(days, 30)))
    row = {
        "org_id": org_id,
        "code": code,
        "label": label[:80],
        "note": (note or "")[:280],
        "expires_at": expires.isoformat(),
        "max_messages": max(1, min(max_messages, 200)),
        "max_calls": max(0, min(max_calls, 5)),
    }
    res = get_supabase().table("guest_passes").insert(row).execute()
    return res.data[0]


def list_passes() -> list[dict]:
    res = (
        get_supabase().table("guest_passes").select("*")
        .order("created_at", desc=True).limit(100).execute()
    )
    return res.data or []


def find_by_label(label: str) -> dict | None:
    res = get_supabase().table("guest_passes").select("*").eq("label", label).execute()
    return res.data[0] if res.data else None


def set_revoked(pass_id: str, revoked: bool) -> None:
    """Revoke, or put a pass back into service."""
    get_supabase().table("guest_passes").update({"revoked": revoked}).eq("id", pass_id).execute()


def revoke_pass(pass_id: str) -> None:
    set_revoked(pass_id, True)


def delete_pass(pass_id: str) -> None:
    """Gone for good. Usage rows cascade with it."""
    get_supabase().table("guest_passes").delete().eq("id", pass_id).execute()


def _fetch(code: str) -> dict | None:
    res = (
        get_supabase().table("guest_passes").select("*")
        .eq("code", (code or "").strip().upper()).execute()
    )
    return res.data[0] if res.data else None


def redeem(code: str) -> tuple[dict | None, str]:
    """Validate a code. Returns (pass_row, error_message)."""
    row = _fetch(code)
    if not row:
        return None, "That code isn't valid."
    if row["revoked"]:
        return None, "That code has been revoked."

    expires = datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00"))
    if expires <= datetime.now(timezone.utc):
        return None, "That code has expired."
    if row["used_messages"] >= row["max_messages"]:
        return None, "That code has reached its message limit."

    return row, ""


# ── Session tokens ─────────────────────────────────────────────────────
# Signed and stateless so a guest turn needs no extra round trip, but the
# pass is re-read on every request so revoking takes effect immediately.

def _secret() -> bytes:
    return (get_settings().jwt_secret or "kaia-guest").encode()


def issue_session(pass_id: str) -> str:
    payload = {
        "pid": pass_id,
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)).timestamp()),
    }
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(_secret(), raw.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{raw}.{sig}"


def read_session(token: str) -> str | None:
    """Returns the pass id, or None if the token is bad or expired."""
    try:
        raw, sig = (token or "").split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(hmac.new(_secret(), raw.encode(), hashlib.sha256).hexdigest()[:32], sig):
        return None
    try:
        padded = raw + "=" * (-len(raw) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
    except Exception:
        return None
    if payload.get("exp", 0) < datetime.now(timezone.utc).timestamp():
        return None
    return payload.get("pid")


# ── Metering ───────────────────────────────────────────────────────────

def _count_today(kind: str) -> int:
    midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    res = (
        get_supabase().table("guest_events").select("id", count="exact")
        .eq("kind", kind).gte("created_at", midnight.isoformat()).execute()
    )
    return res.count or 0


def check_quota(pass_row: dict, kind: str) -> str:
    """Empty string means allowed, otherwise the reason to show the guest."""
    if kind == "message":
        if pass_row["used_messages"] >= pass_row["max_messages"]:
            return "You've used all the messages on this code."
        if _count_today("message") >= DAILY_MESSAGE_CEILING:
            return "Kaia has hit today's global limit. Try again tomorrow."
    elif kind == "call":
        if pass_row["used_calls"] >= pass_row["max_calls"]:
            return "This code has already used its callback."
        if _count_today("call") >= DAILY_CALL_CEILING:
            return "All of today's callbacks are used up. Try again tomorrow."
    return ""


def record(pass_id: str, kind: str, detail: str = "", cost_usd: float = 0.0) -> None:
    db = get_supabase()
    db.table("guest_events").insert({
        "pass_id": pass_id, "kind": kind,
        "detail": (detail or "")[:200], "cost_usd": cost_usd,
    }).execute()

    row = db.table("guest_passes").select("used_messages,used_calls,first_used_at") \
        .eq("id", pass_id).execute().data
    if not row:
        return
    cur = row[0]
    now = datetime.now(timezone.utc).isoformat()
    patch: dict = {"last_used_at": now}
    if not cur.get("first_used_at"):
        patch["first_used_at"] = now
    if kind == "message":
        patch["used_messages"] = cur["used_messages"] + 1
    elif kind == "call":
        patch["used_calls"] = cur["used_calls"] + 1
    db.table("guest_passes").update(patch).eq("id", pass_id).execute()


def remaining(pass_row: dict) -> dict:
    return {
        "messages": max(0, pass_row["max_messages"] - pass_row["used_messages"]),
        "calls": max(0, pass_row["max_calls"] - pass_row["used_calls"]),
        "calls_today_left": max(0, DAILY_CALL_CEILING - _count_today("call")),
    }


def _demo() -> None:
    """Token signing round-trips and rejects tampering."""
    import os
    os.environ.setdefault("JWT_SECRET", "test-secret")

    tok = issue_session("abc-123")
    assert read_session(tok) == "abc-123"
    assert read_session(tok[:-1] + ("x" if tok[-1] != "x" else "y")) is None
    assert read_session("garbage") is None
    assert read_session("") is None

    raw, sig = tok.split(".", 1)
    forged = base64.urlsafe_b64encode(json.dumps(
        {"pid": "someone-else", "exp": 9999999999}
    ).encode()).decode().rstrip("=")
    assert read_session(f"{forged}.{sig}") is None, "forged payload accepted"

    c = make_code("Amazon")
    assert c.startswith("AMAZ-") and len(c) == 9, c
    assert make_code("").startswith("KAIA-")
    assert "0" not in c and "O" not in c
    print("ok")


if __name__ == "__main__":
    _demo()
