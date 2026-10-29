"""Auth middleware — validates Supabase JWT from frontend."""

from fastapi import Request, HTTPException
from app.config import get_settings
import httpx


async def get_current_user(request: Request) -> dict:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Missing auth token")

    token = auth_header[7:]
    s = get_settings()

    # Verify with Supabase
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

    # Get org_id from users table
    from app.database import get_supabase
    db = get_supabase()
    user_row = db.table("users").select("org_id, role").eq("id", user_id).execute()

    org_id = None
    role = "admin"
    if user_row.data:
        org_id = user_row.data[0].get("org_id")
        role = user_row.data[0].get("role", "admin")

    return {
        "user_id": user_id,
        "email": email,
        "org_id": org_id,
        "role": role,
    }
