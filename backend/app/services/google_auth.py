"""Google OAuth 2.0 — authorization code flow, token storage, refresh."""

import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
from google.oauth2.credentials import Credentials
from app.config import get_settings
from app.database import get_supabase
from app.encryption import encrypt_token, decrypt_token
import httpx

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
]


def _parse_expiry(value) -> datetime | None:
    """Stored ISO timestamp -> naive UTC, which is what google-auth compares."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def get_authorization_url() -> str:
    s = get_settings()
    params = urlencode({
        "client_id": s.google_client_id,
        "redirect_uri": s.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    })
    return f"https://accounts.google.com/o/oauth2/auth?{params}"


async def handle_oauth_callback(code: str, user_id: str, org_id: str) -> dict:
    s = get_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": s.google_client_id,
            "client_secret": s.google_client_secret,
            "redirect_uri": s.google_redirect_uri,
            "grant_type": "authorization_code",
        })
    if resp.status_code != 200:
        raise ValueError(f"Token exchange failed: {resp.text[:200]}")

    tokens = resp.json()
    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token")

    # Record when this access token dies. Without it google-auth reports
    # expired=False forever and the refresh token is never used.
    expiry = None
    if tokens.get("expires_in"):
        expiry = (
            datetime.now(timezone.utc) + timedelta(seconds=int(tokens["expires_in"]))
        ).isoformat()

    db = get_supabase()
    db.table("integrations").upsert({
        "user_id": user_id,
        "org_id": org_id,
        "provider": "google",
        "access_token_encrypted": encrypt_token(access_token),
        "refresh_token_encrypted": encrypt_token(refresh_token) if refresh_token else None,
        "token_expiry": expiry,
        "scopes": SCOPES,
        "status": "active",
    }, on_conflict="user_id,provider").execute()

    return {"success": True, "scopes": SCOPES}


async def get_google_credentials(user_id: str, org_id: str) -> Credentials | None:
    db = get_supabase()
    result = db.table("integrations") \
        .select("*") \
        .eq("user_id", user_id) \
        .eq("provider", "google") \
        .eq("status", "active") \
        .single() \
        .execute()

    if not result.data:
        return None

    row = result.data
    s = get_settings()

    try:
        access_token = decrypt_token(row["access_token_encrypted"])
    except ValueError:
        db.table("integrations").update({"status": "revoked"}).eq("id", row["id"]).execute()
        return None

    refresh_token = None
    if row.get("refresh_token_encrypted"):
        try:
            refresh_token = decrypt_token(row["refresh_token_encrypted"])
        except ValueError:
            pass

    stored_expiry = _parse_expiry(row.get("token_expiry"))

    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=s.google_client_id,
        client_secret=s.google_client_secret,
        scopes=row.get("scopes") or SCOPES,
        # google-auth compares this against utcnow, so it must be naive UTC.
        expiry=stored_expiry,
    )

    # Refresh when it has expired, when it is about to, or when we simply
    # don't know — rows written before expiry was stored have no value, and
    # treating unknown as "still valid" is what let the token go stale.
    needs_refresh = (
        stored_expiry is None
        or creds.expired
        or stored_expiry <= datetime.utcnow() + timedelta(seconds=120)
    )

    if needs_refresh and refresh_token:
        try:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            db.table("integrations").update({
                "access_token_encrypted": encrypt_token(creds.token),
                "token_expiry": creds.expiry.isoformat() if creds.expiry else None,
                "status": "active",
            }).eq("id", row["id"]).execute()
        except Exception:
            logger.exception("google: refresh failed for user %s", user_id)
            db.table("integrations").update({"status": "expired"}).eq("id", row["id"]).execute()
            return None
    elif needs_refresh and not refresh_token:
        # Nothing we can do without a refresh token — the user must reconnect.
        db.table("integrations").update({"status": "expired"}).eq("id", row["id"]).execute()
        return None

    return creds


async def revoke_google(user_id: str, org_id: str) -> dict:
    db = get_supabase()
    db.table("integrations") \
        .update({"status": "revoked"}) \
        .eq("user_id", user_id) \
        .eq("provider", "google") \
        .execute()
    return {"success": True}
