"""Google OAuth 2.0 — authorization code flow, token storage, refresh."""

from datetime import datetime, timezone
from urllib.parse import urlencode
from google.oauth2.credentials import Credentials
from app.config import get_settings
from app.database import get_supabase
from app.encryption import encrypt_token, decrypt_token
import httpx

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
]


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

    db = get_supabase()
    db.table("integrations").upsert({
        "user_id": user_id,
        "org_id": org_id,
        "provider": "google",
        "access_token_encrypted": encrypt_token(access_token),
        "refresh_token_encrypted": encrypt_token(refresh_token) if refresh_token else None,
        "token_expiry": None,
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

    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=s.google_client_id,
        client_secret=s.google_client_secret,
        scopes=row.get("scopes") or SCOPES,
    )

    if creds.expired and creds.refresh_token:
        try:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            db.table("integrations").update({
                "access_token_encrypted": encrypt_token(creds.token),
                "token_expiry": creds.expiry.isoformat() if creds.expiry else None,
            }).eq("id", row["id"]).execute()
        except Exception:
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
