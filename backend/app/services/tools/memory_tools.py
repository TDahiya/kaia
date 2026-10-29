"""Memory tools — search, add, update, delete personal memories."""

from app.database import get_supabase
from app.services.tool_registry import ToolDef, registry

# These tools receive user_id and org_id via context injection in the route layer


async def search_memories(query: str, category: str = "", limit: int = 10, **ctx) -> dict:
    db = get_supabase()
    q = db.table("memories") \
        .select("id, category, content, importance, updated_at") \
        .eq("org_id", ctx.get("org_id", "")) \
        .eq("is_active", True) \
        .order("importance", desc=True) \
        .limit(limit)

    if category:
        q = q.eq("category", category)

    # Simple text search — Supabase full-text can be added later
    result = q.execute()
    matches = [r for r in result.data if query.lower() in r["content"].lower()] if query else result.data
    return {"memories": matches[:limit], "count": len(matches)}


async def add_memory(content: str, category: str = "general", importance: int = 5, **ctx) -> dict:
    db = get_supabase()
    result = db.table("memories").insert({
        "org_id": ctx.get("org_id", ""),
        "user_id": ctx.get("user_id", ""),
        "category": category,
        "content": content,
        "importance": max(1, min(10, importance)),
        "source": ctx.get("conversation_id", "assistant"),
    }).execute()
    return {"success": True, "id": result.data[0]["id"]}


async def update_memory(memory_id: str, content: str = "", importance: int | None = None, is_active: bool | None = None, **ctx) -> dict:
    db = get_supabase()
    updates: dict = {}
    if content:
        updates["content"] = content
    if importance is not None:
        updates["importance"] = max(1, min(10, importance))
    if is_active is not None:
        updates["is_active"] = is_active
    if not updates:
        return {"error": "Nothing to update"}

    db.table("memories") \
        .update(updates) \
        .eq("id", memory_id) \
        .eq("org_id", ctx.get("org_id", "")) \
        .execute()
    return {"success": True}


async def delete_memory(memory_id: str, **ctx) -> dict:
    db = get_supabase()
    db.table("memories") \
        .update({"is_active": False}) \
        .eq("id", memory_id) \
        .eq("org_id", ctx.get("org_id", "")) \
        .execute()
    return {"success": True}


for tool in [
    ToolDef(
        name="search_memories",
        description="Search the user's personal memory for stored facts, preferences, and information.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term"},
                "category": {"type": "string", "enum": ["preference", "fact", "project", "contact", "general"], "description": "Filter by category"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
        executor=search_memories,
        category="memory",
    ),
    ToolDef(
        name="add_memory",
        description="Store a new fact, preference, or important information about the user.",
        input_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The information to remember"},
                "category": {"type": "string", "enum": ["preference", "fact", "project", "contact", "general"]},
                "importance": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
            },
            "required": ["content"],
        },
        executor=add_memory,
        category="memory",
    ),
    ToolDef(
        name="update_memory",
        description="Update an existing memory entry.",
        input_schema={
            "type": "object",
            "properties": {
                "memory_id": {"type": "string"},
                "content": {"type": "string"},
                "importance": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            "required": ["memory_id"],
        },
        executor=update_memory,
        category="memory",
    ),
    ToolDef(
        name="delete_memory",
        description="Delete (deactivate) a memory entry.",
        input_schema={
            "type": "object",
            "properties": {"memory_id": {"type": "string"}},
            "required": ["memory_id"],
        },
        executor=delete_memory,
        category="memory",
    ),
]:
    registry.register(tool)
