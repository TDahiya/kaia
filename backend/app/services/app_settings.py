"""Runtime-editable settings backed by the app_settings table.

A stored row overrides the matching environment variable, so the owner can
change things like their phone number from the UI without a redeploy.
"""

import re
from app.config import get_settings
from app.database import get_supabase

OWNER_PHONE = "owner_phone_e164"

# E.164: leading +, first digit 1-9, 8-15 digits total.
E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")


def get_value(key: str) -> str | None:
    try:
        r = get_supabase().table("app_settings").select("value").eq("key", key).execute()
        return r.data[0]["value"] if r.data else None
    except Exception:
        # Table missing or DB unreachable — fall back to env.
        return None


def set_value(key: str, value: str) -> None:
    get_supabase().table("app_settings").upsert(
        {"key": key, "value": value}, on_conflict="key"
    ).execute()


def get_owner_phone() -> str:
    """The one number Kaia may call. DB row wins, env is the fallback."""
    return get_value(OWNER_PHONE) or get_settings().owner_phone_e164 or ""


def normalize_phone(raw: str) -> str:
    """Strip formatting and validate. Raises ValueError if not E.164."""
    cleaned = re.sub(r"[\s()\-.]", "", (raw or "").strip())
    if not E164_RE.match(cleaned):
        raise ValueError("Phone must be E.164 format, e.g. +353871234567")
    return cleaned


def _demo() -> None:
    assert normalize_phone("+353 87 123 4567") == "+353871234567"
    assert normalize_phone(" +1 (555) 010-1234 ") == "+15550101234"
    for bad in ["", "353894533899", "+0353894533899", "+353", "+abc", "+1234567890123456"]:
        try:
            normalize_phone(bad)
            raise AssertionError(f"should have rejected {bad!r}")
        except ValueError:
            pass
    print("ok")


if __name__ == "__main__":
    _demo()
