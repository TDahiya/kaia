"""Memory management routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.auth import get_current_user
from app.database import get_supabase
from app.services.memory_summarizer import run_weekly_summary

router = APIRouter(prefix="/api/memories", tags=["memories"])


@router.get("")
async def list_memories(
    category: str = "", active_only: bool = True, limit: int = 50,
    user: dict = Depends(get_current_user),
):
    db = get_supabase()
    q = db.table("memories") \
        .select("*") \
        .eq("org_id", user["org_id"]) \
        .order("importance", desc=True) \
        .limit(limit)
    if active_only:
        q = q.eq("is_active", True)
    if category:
        q = q.eq("category", category)
    result = q.execute()
    return {"memories": result.data}


class MemoryCreate(BaseModel):
    content: str
    category: str = "general"
    importance: int = 5


@router.post("")
async def create_memory(req: MemoryCreate, user: dict = Depends(get_current_user)):
    db = get_supabase()
    result = db.table("memories").insert({
        "org_id": user["org_id"],
        "user_id": user["user_id"],
        "category": req.category,
        "content": req.content,
        "importance": max(1, min(10, req.importance)),
        "source": "manual",
    }).execute()
    return {"memory": result.data[0]}


class MemoryUpdate(BaseModel):
    content: str | None = None
    category: str | None = None
    importance: int | None = None
    is_active: bool | None = None


@router.patch("/{memory_id}")
async def update_memory(memory_id: str, req: MemoryUpdate, user: dict = Depends(get_current_user)):
    db = get_supabase()
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "Nothing to update")
    result = db.table("memories").update(updates).eq("id", memory_id).eq("org_id", user["org_id"]).execute()
    if not result.data:
        raise HTTPException(404, "Memory not found")
    return {"memory": result.data[0]}


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str, user: dict = Depends(get_current_user)):
    db = get_supabase()
    db.table("memories").update({"is_active": False}).eq("id", memory_id).eq("org_id", user["org_id"]).execute()
    return {"success": True}


@router.get("/summaries")
async def list_summaries(limit: int = 10, user: dict = Depends(get_current_user)):
    db = get_supabase()
    result = db.table("weekly_summaries") \
        .select("*") \
        .eq("org_id", user["org_id"]) \
        .order("week_start", desc=True) \
        .limit(limit) \
        .execute()
    return {"summaries": result.data}


@router.post("/summarize-now")
async def trigger_summarize(user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    result = await run_weekly_summary(user["user_id"], user["org_id"])
    return result
