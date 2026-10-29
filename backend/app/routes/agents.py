"""Agent CRUD routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.auth import get_current_user
from app.database import get_supabase

router = APIRouter(prefix="/api/agents", tags=["agents"])


class AgentCreate(BaseModel):
    name: str
    description: str = ""
    system_prompt: str = ""
    personality: str = ""
    model_fast: str = "claude-haiku-5-5"
    model_standard: str = "claude-sonnet-5-5"
    model_premium: str = "claude-opus-5-5"
    voice_id: str = "aura-2-theia-en"
    language: str = "en"
    max_tool_calls_per_turn: int = 15


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    personality: str | None = None
    model_fast: str | None = None
    model_standard: str | None = None
    model_premium: str | None = None
    voice_id: str | None = None
    language: str | None = None
    max_tool_calls_per_turn: int | None = None
    is_default: bool | None = None


@router.get("")
async def list_agents(user: dict = Depends(get_current_user)):
    db = get_supabase()
    result = db.table("agents") \
        .select("*") \
        .eq("org_id", user["org_id"]) \
        .order("created_at", desc=True) \
        .execute()
    return {"agents": result.data}


@router.post("")
async def create_agent(req: AgentCreate, user: dict = Depends(get_current_user)):
    db = get_supabase()
    result = db.table("agents").insert({
        "org_id": user["org_id"],
        **req.model_dump(),
    }).execute()
    return {"agent": result.data[0]}


@router.get("/{agent_id}")
async def get_agent(agent_id: str, user: dict = Depends(get_current_user)):
    db = get_supabase()
    result = db.table("agents").select("*").eq("id", agent_id).eq("org_id", user["org_id"]).single().execute()
    if not result.data:
        raise HTTPException(404, "Agent not found")
    return {"agent": result.data}


@router.patch("/{agent_id}")
async def update_agent(agent_id: str, req: AgentUpdate, user: dict = Depends(get_current_user)):
    db = get_supabase()
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "Nothing to update")

    if updates.get("is_default"):
        db.table("agents").update({"is_default": False}).eq("org_id", user["org_id"]).execute()

    result = db.table("agents").update(updates).eq("id", agent_id).eq("org_id", user["org_id"]).execute()
    if not result.data:
        raise HTTPException(404, "Agent not found")
    return {"agent": result.data[0]}


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, user: dict = Depends(get_current_user)):
    db = get_supabase()
    db.table("agents").delete().eq("id", agent_id).eq("org_id", user["org_id"]).execute()
    return {"success": True}


@router.post("/{agent_id}/clone")
async def clone_agent(agent_id: str, user: dict = Depends(get_current_user)):
    db = get_supabase()
    source = db.table("agents").select("*").eq("id", agent_id).eq("org_id", user["org_id"]).single().execute()
    if not source.data:
        raise HTTPException(404, "Agent not found")

    clone_data = {k: v for k, v in source.data.items() if k not in ("id", "created_at", "updated_at")}
    clone_data["name"] = f"{clone_data['name']} (Copy)"
    clone_data["is_default"] = False

    result = db.table("agents").insert(clone_data).execute()
    return {"agent": result.data[0]}
