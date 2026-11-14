"""Chat routes — text and tool-augmented conversations."""

import json
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.auth import require_owner
from app.database import get_supabase
from app.services.ai_brain import (
    chat_with_tools, build_system_prompt, ModelTier,
    get_async_openai, get_model_id, classify_complexity, _convert_tools_for_openai,
    completion_params,
)
from app.services.tool_registry import registry
from app.services.usage_tracker import check_spend_limit
from app.services import documents as document_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"

DEFAULT_SYSTEM_PROMPT = """You are Kaia — sharp, warm, a little witty. Not a corporate chatbot. A brilliant friend who happens to have access to calendars, emails, maps, and a perfect memory.

## How you talk
- Like a text from a smart friend. Short, direct, personality showing.
- Confident — you know, or you say you don't. No "I think" or "perhaps".
- Brief. One to three sentences unless they asked for more.
- Match their energy — rushed → snappy, chatting → chat back.

## NEVER do this
- No numbered lists. No bullet points. No bold text. Write in plain sentences.
- No sign-offs: "Happy driving!", "Enjoy your trip!", "Have a great day!", "Let me know if you need anything!" — just stop when you're done.
- No filler: "Great question!", "Of course!", "Absolutely!", "I'd be happy to help!" — just do the thing.
- No hedging: "Unfortunately", "I'm sorry but", "I wasn't able to" — be straight. "Couldn't find that" is fine.
- No self-narration: "Let me look that up", "I'll check that for you" — just do it and give the answer.
- No "shall I proceed?" or "would you like me to" — just do it.

## How you work
- ACT FIRST. "Create a meeting at 11am" → call the tool. Today if no date, 30min default, sensible title. Smart defaults, not clarifying questions.
- Only ask when you genuinely can't infer something critical.

## Saying something is done
An action counts as done ONLY when a tool call returned a successful result
in this conversation. Intending to do it is not doing it.
- Never write "scheduled", "created", "sent", "saved", "added" or "booked"
  unless the matching tool ran and succeeded. No tool call means it did not happen.
- A statement like "appointment tomorrow 3pm for my car service" is an
  instruction. Call create_calendar_event. Do not reply as though you had.
- If a tool returns an error, say plainly what failed and what the user
  should do. If it mentions an expired or revoked token, tell them to
  reconnect Google in Settings. Never retry silently and never paper over it.

## Links
When a tool returns a URL, ALWAYS include it as a clickable markdown link. The link IS the point — never say "I found directions" without it.

## Memory
When they share something personal — save it with add_memory. Don't store trivia.

## Tools
Calendar, email, CRM, weather, maps, memory. Use them without announcing it."""


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    agent_id: str | None = None
    mode: str = "text"
    document_ids: list[str] = []


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str
    model: str
    tier: str
    tokens_in: int
    tokens_out: int
    estimated_cost_usd: float
    tool_calls_made: list[str] = []


async def _prepare_turn(req: ChatRequest, user: dict):
    """Everything both the streaming and non-streaming paths need.

    Resolves the conversation, adopts attachments, stores the user message,
    and assembles the prompt + history. Returns a small bundle.
    """
    org_id = user["org_id"]
    user_id = user["user_id"]

    if not org_id:
        raise HTTPException(400, "User not associated with an organization")
    if not await check_spend_limit(org_id):
        raise HTTPException(429, "Monthly spend limit reached")

    db = get_supabase()

    if req.conversation_id:
        conv = db.table("conversations").select("id, agent_id") \
            .eq("id", req.conversation_id).eq("org_id", org_id).single().execute()
        if not conv.data:
            raise HTTPException(404, "Conversation not found")
        conversation_id = req.conversation_id
        agent_id = conv.data.get("agent_id")
    else:
        agent_id = req.agent_id
        conv = db.table("conversations").insert({
            "org_id": org_id, "user_id": user_id, "agent_id": agent_id,
            "mode": req.mode, "title": req.message[:80],
        }).execute()
        conversation_id = conv.data[0]["id"]

    for doc_id in req.document_ids:
        db.table("documents").update({"conversation_id": conversation_id}) \
            .eq("id", doc_id).eq("org_id", org_id).execute()

    db.table("messages").insert({
        "conversation_id": conversation_id, "role": "user", "content": req.message,
    }).execute()

    system_prompt = DEFAULT_SYSTEM_PROMPT
    if agent_id:
        agent = db.table("agents").select("system_prompt").eq("id", agent_id).single().execute()
        if agent.data and agent.data.get("system_prompt"):
            system_prompt = agent.data["system_prompt"]

    memories_result = db.table("memories").select("content") \
        .eq("org_id", org_id).eq("is_active", True) \
        .order("importance", desc=True).limit(15).execute()
    full_prompt = build_system_prompt(system_prompt, [m["content"] for m in memories_result.data])

    attached = document_service.list_documents(conversation_id, org_id)
    if attached:
        lines = ["\n\n## Attached files"]
        for d in attached:
            lines.append(f"- {d['filename']} (id: {d['id']}, type: {d['kind']})")
        if any(d["kind"] == "table" for d in attached):
            lines.append(
                "\nFor any spreadsheet question, call inspect_document, then "
                "query_document with pandas code. Never work a total, count or "
                "average out yourself from sample rows — run the code."
            )
        lines.append(
            "\nTo read a PDF or text attachment in full, call inspect_document "
            "with its id. Do not claim you cannot see an attached file."
        )
        full_prompt += "\n".join(lines)

    history = db.table("messages").select("role, content") \
        .eq("conversation_id", conversation_id).order("created_at").limit(20).execute()
    messages = [
        {"role": m["role"], "content": m["content"]}
        for m in history.data if m["role"] in ("user", "assistant")
    ]

    async def execute_tool(name: str, args: dict):
        args["user_id"] = user_id
        args["org_id"] = org_id
        args["conversation_id"] = conversation_id
        return await registry.execute(name, args, org_id=org_id, conversation_id=conversation_id)

    return {
        "db": db,
        "org_id": org_id,
        "conversation_id": conversation_id,
        "prompt": full_prompt,
        "messages": messages,
        "execute_tool": execute_tool,
    }


@router.post("/stream")
async def stream_message(req: ChatRequest, user: dict = Depends(require_owner)):
    """Server-sent events: text arrives as the model writes it."""
    turn = await _prepare_turn(req, user)

    async def events():
        yield _sse({"type": "meta", "conversation_id": turn["conversation_id"]})

        client = get_async_openai()
        tier = classify_complexity(req.message)
        model = get_model_id(tier)
        oai_tools = _convert_tools_for_openai(registry.list_definitions())

        oai_msgs: list[dict] = [{"role": "system", "content": turn["prompt"]}]
        oai_msgs += [m for m in turn["messages"] if isinstance(m.get("content"), str)]

        parts: list[str] = []
        tools_made: list[str] = []
        tokens_in = tokens_out = 0

        try:
            for _ in range(6):
                stream = await client.chat.completions.create(
                    model=model, messages=oai_msgs, tools=oai_tools,
                    stream=True, stream_options={"include_usage": True},
                    **completion_params(model, 1500, has_tools=True),
                )

                text = ""
                tc_map: dict[int, dict] = {}
                finish = None

                async for chunk in stream:
                    if chunk.usage:
                        tokens_in += chunk.usage.prompt_tokens or 0
                        tokens_out += chunk.usage.completion_tokens or 0
                    c = chunk.choices[0] if chunk.choices else None
                    if not c:
                        continue
                    if c.finish_reason:
                        finish = c.finish_reason
                    d = c.delta
                    if d and d.content:
                        text += d.content
                        parts.append(d.content)
                        yield _sse({"type": "delta", "text": d.content})
                    if d and d.tool_calls:
                        for tcd in d.tool_calls:
                            slot = tc_map.setdefault(tcd.index, {"id": "", "name": "", "args": ""})
                            if tcd.id:
                                slot["id"] = tcd.id
                            if tcd.function:
                                if tcd.function.name:
                                    slot["name"] = tcd.function.name
                                if tcd.function.arguments:
                                    slot["args"] += tcd.function.arguments

                if finish != "tool_calls" or not tc_map:
                    break

                oai_msgs.append({
                    "role": "assistant", "content": text or None,
                    "tool_calls": [
                        {"id": tc_map[i]["id"], "type": "function",
                         "function": {"name": tc_map[i]["name"], "arguments": tc_map[i]["args"]}}
                        for i in sorted(tc_map)
                    ],
                })

                for i in sorted(tc_map):
                    tc = tc_map[i]
                    tools_made.append(tc["name"])
                    # Surfacing this lets the UI say what it is doing during
                    # a slow tool call instead of showing a frozen cursor.
                    yield _sse({"type": "tool", "name": tc["name"]})
                    try:
                        args = json.loads(tc["args"]) if tc["args"] else {}
                    except json.JSONDecodeError:
                        args = {}
                    try:
                        result = await turn["execute_tool"](tc["name"], args)
                        content = result if isinstance(result, str) else json.dumps(result)
                    except Exception as e:
                        content = f"Error: {e}"
                    oai_msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": content})

        except Exception as e:
            yield _sse({"type": "error", "message": str(e)})
            return

        reply = "".join(parts)
        turn["db"].table("messages").insert({
            "conversation_id": turn["conversation_id"],
            "role": "assistant", "content": reply,
            "model_used": model, "tokens_in": tokens_in, "tokens_out": tokens_out,
        }).execute()

        yield _sse({
            "type": "done", "model": model, "tier": tier.value,
            "tokens_in": tokens_in, "tokens_out": tokens_out,
            "tool_calls_made": tools_made,
        })

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("", response_model=ChatResponse)
async def send_message(req: ChatRequest, user: dict = Depends(require_owner)):
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

    # A file can be attached before the first message exists, so adopt any
    # the client names into this conversation before building the prompt.
    for doc_id in req.document_ids:
        db.table("documents").update({"conversation_id": conversation_id}) \
            .eq("id", doc_id).eq("org_id", org_id).execute()

    # Store user message
    db.table("messages").insert({
        "conversation_id": conversation_id,
        "role": "user",
        "content": req.message,
    }).execute()

    # Load agent prompt
    system_prompt = DEFAULT_SYSTEM_PROMPT
    if agent_id:
        agent = db.table("agents").select("system_prompt").eq("id", agent_id).single().execute()
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

    # Tell the model which files are on this conversation. Spreadsheets get
    # an explicit instruction to compute rather than read off the preview —
    # the preview is the first few rows, not the data.
    attached = document_service.list_documents(conversation_id, org_id)
    if attached:
        lines = ["\n\n## Attached files"]
        for d in attached:
            lines.append(f"- {d['filename']} (id: {d['id']}, type: {d['kind']})")
        if any(d["kind"] == "table" for d in attached):
            lines.append(
                "\nFor any spreadsheet question, call inspect_document, then "
                "query_document with pandas code. Never work a total, count or "
                "average out yourself from sample rows — run the code."
            )
        full_prompt += "\n".join(lines)

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
async def list_conversations(limit: int = 20, user: dict = Depends(require_owner)):
    db = get_supabase()
    result = db.table("conversations") \
        .select("id, title, mode, started_at, ended_at") \
        .eq("org_id", user["org_id"]) \
        .order("started_at", desc=True) \
        .limit(limit) \
        .execute()
    return {"conversations": result.data}


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str, user: dict = Depends(require_owner)):
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


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, user: dict = Depends(require_owner)):
    db = get_supabase()
    conv = db.table("conversations").select("id").eq("id", conversation_id).eq("org_id", user["org_id"]).execute()
    if not conv.data:
        raise HTTPException(404, "Conversation not found")

    # Messages have no cascade on conversation_id, so clear them first.
    db.table("messages").delete().eq("conversation_id", conversation_id).execute()
    db.table("conversations").delete().eq("id", conversation_id).execute()
    return {"success": True}
