"""Weekly memory summarization — compacts conversations into durable memories."""

from datetime import datetime, timedelta, timezone
from app.database import get_supabase
from app.services.ai_brain import chat, ModelTier, build_system_prompt

SUMMARIZER_PROMPT = """You are a personal memory manager. Given a week's conversation history,
extract the important durable facts, preferences, decisions, and project updates.

Output a JSON object with:
- "memories": list of objects with "content" (string), "category" (preference|fact|project|contact|general), "importance" (1-10)
- "weekly_summary": a concise paragraph summarizing the week's key developments
- "obsolete_memory_ids": list of memory IDs that should be deactivated (outdated or superseded)

Focus on what matters long-term. Skip small talk, repeated greetings, and transient requests.
Do NOT include passwords, API keys, or sensitive credentials."""


async def run_weekly_summary(user_id: str, org_id: str) -> dict:
    db = get_supabase()
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    week_start = week_ago.date()
    week_end = now.date()

    # Check if already run for this week (idempotent)
    existing = db.table("weekly_summaries") \
        .select("id") \
        .eq("user_id", user_id) \
        .eq("week_start", week_start.isoformat()) \
        .execute()
    if existing.data:
        return {"status": "already_completed", "id": existing.data[0]["id"]}

    # Fetch recent conversations and messages
    convos = db.table("conversations") \
        .select("id") \
        .eq("org_id", org_id) \
        .gte("started_at", week_ago.isoformat()) \
        .execute()

    if not convos.data:
        return {"status": "no_conversations", "conversations_processed": 0}

    convo_ids = [c["id"] for c in convos.data]
    all_messages = []
    for cid in convo_ids:
        msgs = db.table("messages") \
            .select("role, content, created_at") \
            .eq("conversation_id", cid) \
            .order("created_at") \
            .limit(200) \
            .execute()
        all_messages.extend(msgs.data)

    if not all_messages:
        return {"status": "no_messages", "conversations_processed": 0}

    # Get existing memories for context
    existing_memories = db.table("memories") \
        .select("id, content, category") \
        .eq("org_id", org_id) \
        .eq("is_active", True) \
        .limit(50) \
        .execute()

    # Build conversation digest (compact)
    digest_lines = []
    for m in all_messages[:500]:
        role = m["role"]
        content = m["content"][:200]
        digest_lines.append(f"[{role}] {content}")
    digest = "\n".join(digest_lines)

    existing_mem_text = "\n".join(
        f"- [{m['id']}] ({m['category']}) {m['content']}"
        for m in existing_memories.data
    )

    messages = [{
        "role": "user",
        "content": f"""Here are this week's conversations:\n\n{digest}\n\n
Existing memories:\n{existing_mem_text}\n\n
Extract new memories, summarize the week, and flag obsolete memories.""",
    }]

    resp = await chat(
        messages=messages,
        system_prompt=SUMMARIZER_PROMPT,
        tier=ModelTier.STANDARD,
        org_id=org_id,
    )

    # Parse response
    import json
    try:
        data = json.loads(resp.content)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code blocks
        content = resp.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return {"status": "parse_error", "raw_response": resp.content[:500]}

    # Store new memories
    new_count = 0
    for mem in data.get("memories", []):
        db.table("memories").insert({
            "org_id": org_id,
            "user_id": user_id,
            "category": mem.get("category", "general"),
            "content": mem["content"],
            "importance": mem.get("importance", 5),
            "source": "weekly_summary",
        }).execute()
        new_count += 1

    # Deactivate obsolete memories
    for mid in data.get("obsolete_memory_ids", []):
        db.table("memories") \
            .update({"is_active": False}) \
            .eq("id", mid) \
            .eq("org_id", org_id) \
            .execute()

    # Store weekly summary
    summary_text = data.get("weekly_summary", resp.content[:500])
    db.table("weekly_summaries").insert({
        "org_id": org_id,
        "user_id": user_id,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "summary": summary_text,
        "memories_updated": new_count,
        "conversations_processed": len(convo_ids),
    }).execute()

    return {
        "status": "completed",
        "new_memories": new_count,
        "conversations_processed": len(convo_ids),
        "obsolete_deactivated": len(data.get("obsolete_memory_ids", [])),
    }
