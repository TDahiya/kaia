"""Integration routes — Google OAuth, connection status."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from app.auth import get_current_user
from app.database import get_supabase
from app.services.google_auth import get_authorization_url, handle_oauth_callback, revoke_google
from app.config import get_settings

router = APIRouter(prefix="/api/auth", tags=["integrations"])


@router.get("/google")
async def google_auth_start(user: dict = Depends(get_current_user)):
    """Returns the Google OAuth URL for the frontend to redirect to."""
    url = get_authorization_url()
    return {"auth_url": url}


@router.get("/google/callback")
async def google_auth_callback(code: str, request: Request):
    """Google OAuth callback — exchanges code for tokens."""
    # In production, use state parameter to map back to user
    # For now, get user from session/cookie
    # This endpoint is hit directly by Google redirect
    s = get_settings()

    # Temporary: extract user context from state or use admin
    db = get_supabase()
    users = db.table("users").select("id, org_id").limit(1).execute()
    if not users.data:
        raise HTTPException(400, "No users configured")

    user_id = users.data[0]["id"]
    org_id = users.data[0]["org_id"]

    try:
        result = await handle_oauth_callback(code, user_id, org_id)
    except Exception as e:
        frontend_url = s.app_base_url
        return RedirectResponse(f"{frontend_url}/settings?google=error&reason={str(e)[:100]}")
    frontend_url = s.app_base_url
    return RedirectResponse(f"{frontend_url}/settings?google=connected")


@router.get("/google/status")
async def google_status(user: dict = Depends(get_current_user)):
    db = get_supabase()
    result = db.table("integrations") \
        .select("status, scopes, updated_at") \
        .eq("user_id", user["user_id"]) \
        .eq("provider", "google") \
        .execute()

    if not result.data:
        return {"connected": False}

    row = result.data[0]
    return {
        "connected": row["status"] == "active",
        "status": row["status"],
        "scopes": row.get("scopes", []),
        "updated_at": row.get("updated_at"),
    }


@router.post("/google/revoke")
async def google_revoke(user: dict = Depends(get_current_user)):
    await revoke_google(user["user_id"], user["org_id"])
    return {"success": True}
