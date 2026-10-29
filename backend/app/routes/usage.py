"""Usage and cost tracking routes."""

from fastapi import APIRouter, Depends
from app.auth import get_current_user
from app.services.usage_tracker import get_monthly_spend
from app.database import get_supabase

router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("")
async def get_usage(user: dict = Depends(get_current_user)):
    spend = await get_monthly_spend(user["org_id"])
    return spend


@router.get("/history")
async def get_usage_history(days: int = 30, user: dict = Depends(get_current_user)):
    from datetime import datetime, timedelta, timezone
    db = get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    result = db.table("usage_events") \
        .select("provider, event_type, quantity, unit, estimated_cost_usd, model, created_at") \
        .eq("org_id", user["org_id"]) \
        .gte("created_at", since) \
        .order("created_at", desc=True) \
        .limit(500) \
        .execute()
    return {"events": result.data}


@router.get("/call-logs")
async def get_call_logs(limit: int = 50, user: dict = Depends(get_current_user)):
    db = get_supabase()
    result = db.table("call_logs") \
        .select("*") \
        .eq("org_id", user["org_id"]) \
        .order("started_at", desc=True) \
        .limit(limit) \
        .execute()
    return {"call_logs": result.data}
