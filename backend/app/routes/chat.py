"""Chat routes — text and tool-augmented conversations."""

import json
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from app.auth import get_current_user
from app.database import get_supabase
from app.services.ai_brain import chat_with_tools, build_system_prompt, ModelTier
from app.services.tool_registry import registry
from app.services.usage_tracker import check_spend_limit

router = APIRouter(prefix="/api/chat", tags=["chat"])

DEFAULT_SYSTEM_PROMPT = """You are Kaia, a helpful personal AI assistant. You are warm, concise, and proactive.
You have access to tools for calendar, email, CRM, weather, and personal memory.
Use tools when they help answer the user's question. Don't make up information — use your tools.
When creating events or sending emails, always confirm with the user first.
Keep responses natural and conversational. If you store a memory, briefly confirm what you remembered."""


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    agent_id: str | None = None
    mode: str = "text"


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str
    model: str
    tier: str
    tokens_in: int
    tokens_out: int
    estimated_cost_usd: float
    tool_calls_made: list[str] = []


@router.post("", response_model=ChatResponse)
async def send_message(req: ChatRequest, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    user_id = user["user_id"]

    if not org_id:
        raise HTTPException(400, "User not associated with an organization")

    if not await check_spend_limit(org_id):
        raise HTTPException(429, "Monthly spend limit reached")

    db = get_supabase()

    # Get or create conversation
    if req.conversation_id:
        conv = db.table("conversations").select("id, agent_id").eq("id", req.conversation_id).eq("org_id", org_id).single().execute()
        if not conv.data:
            raise HTTPException(404, "Conversation not found")
        conversation_id = req.conversation_id
        agent_id = conv.data.get("agent_id")
    else:
        agent_id = req.agent_id
        conv = db.table("conversations").insert({
            "org_id": org_id,
            "user_id": user_id,
            "agent_id": agent_id,
            "mode": req.mode,
            "title": req.message[:80],
        }).execute()
        conversation_id = conv.data[0]["id"]

    # Store user message
    db.table("messages").insert({
        "conversation_id": conversation_id,
        "role": "user",
        "content": req.message,
    }).execute()

    # Load agent prompt
    system_prompt = DEFAULT_SYSTEM_PROMPT
    if agent_id:
        agent = db.table("agents").select("system_prompt, model_fast, model_standard, model_premium").eq("id", agent_id).single().execute()
        if agent.data and agent.data.get("system_prompt"):
            system_prompt = agent.data["system_prompt"]

    # Load memories for context
    memories_result = db.table("memories") \
        .select("content") \
        .eq("org_id", org_id) \
        .eq("is_active", True) \
        .order("importance", desc=True) \
        .limit(15) \
        .execute()
    memory_lines = [m["content"] for m in memories_result.data]
    full_prompt = build_system_prompt(system_prompt, memory_lines)

    # Load recent messages for context (last 20)
    history_result = db.table("messages") \
        .select("role, content") \
        .eq("conversation_id", conversation_id) \
        .order("created_at") \
        .limit(20) \
        .execute()

    messages = []
    for m in history_result.data:
        if m["role"] in ("user", "assistant"):
            messages.append({"role": m["role"], "content": m["content"]})

    # Tool executor with context injection
    async def execute_tool(name: str, args: dict):
        args["user_id"] = user_id
        args["org_id"] = org_id
        args["conversation_id"] = conversation_id
        return await registry.execute(name, args, org_id=org_id, conversation_id=conversation_id)

    # Run AI with tools
    tools_made = []
    resp = await chat_with_tools(
        messages=messages,
        system_prompt=full_prompt,
        tools_definitions=registry.list_definitions(),
        tool_executor=execute_tool,
        org_id=org_id,
    )

    if resp.tool_calls:
        tools_made = [tc["name"] for tc in resp.tool_calls]

    # Store assistant response
    db.table("messages").insert({
        "conversation_id": conversation_id,
        "role": "assistant",
        "content": resp.content,
        "model_used": resp.model,
        "tokens_in": resp.tokens_in,
        "tokens_out": resp.tokens_out,
    }).execute()

    return ChatResponse(
        reply=resp.content,
        conversation_id=conversation_id,
        model=resp.model,
        tier=resp.tier.value,
        tokens_in=resp.tokens_in,
        tokens_out=resp.tokens_out,
        estimated_cost_usd=resp.estimated_cost_usd,
        tool_calls_made=tools_made,
    )


@router.get("/conversations")
async def list_conversations(limit: int = 20, user: dict = Depends(get_current_user)):
    db = get_supabase()
    result = db.table("conversations") \
        .select("id, title, mode, started_at, ended_at") \
        .eq("org_id", user["org_id"]) \
        .order("started_at", desc=True) \
        .limit(limit) \
        .execute()
    return {"conversations": result.data}


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str, user: dict = Depends(get_current_user)):
    db = get_supabase()
    # Verify ownership
    conv = db.table("conversations").select("id").eq("id", conversation_id).eq("org_id", user["org_id"]).execute()
    if not conv.data:
        raise HTTPException(404, "Conversation not found")

    result = db.table("messages") \
        .select("id, role, content, tool_name, model_used, tokens_in, tokens_out, created_at") \
        .eq("conversation_id", conversation_id) \
        .order("created_at") \
        .execute()
    return {"messages": result.data}
