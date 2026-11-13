"""Auth for the owner's surfaces.

Two separate things, and conflating them was a hole: a valid Supabase
token proves *who* you are, not that you are allowed in here. Supabase
sign-up is public, so anyone could register and — because `role` defaulted
to "admin" and nothing compared the email — reach the dashboard, the
agents, the memories and the access-code pages.

`get_current_user` authenticates. `require_owner` authorises, and every
owner-only route depends on that one.
"""

from fastapi import Request, HTTPException, Depends
from app.config import get_settings
import httpx


def _owner_emails() -> set[str]:
    s = get_settings()
    raw = s.owner_email or ""
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


async def get_current_user(request: Request) -> dict:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Missing auth token")

    token = auth_header[7:]
    s = get_settings()

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{s.supabase_url}/auth/v1/user",
            headers={"Authorization": f"Bearer {token}", "apikey": s.supabase_anon_key},
        )
    if resp.status_code != 200:
        raise HTTPException(401, "Invalid token")

    user_data = resp.json()
    user_id = user_data.get("id")
    email = user_data.get("email")

    from app.database import get_supabase
    db = get_supabase()
    user_row = db.table("users").select("org_id, role").eq("id", user_id).execute()

    org_id = None
    # Never default to admin. Membership is decided by the configured owner
    # email, not by the absence of a row.
    role = "guest"
    if user_row.data:
        org_id = user_row.data[0].get("org_id")
        role = user_row.data[0].get("role") or "guest"

    owners = _owner_emails()
    is_owner = bool(email) and email.lower() in owners
    if is_owner:
        role = "admin"

    return {
        "user_id": user_id,
        "email": email,
        "org_id": org_id,
        "role": role,
        "is_owner": is_owner,
    }


async def require_owner(user: dict = Depends(get_current_user)) -> dict:
    """Gate for everything that belongs to the owner alone."""
    if not user.get("is_owner"):
        raise HTTPException(
            403,
            "This area belongs to the owner. Ask Tanishq for an access code "
            "to use the guest portal.",
        )
    return user
