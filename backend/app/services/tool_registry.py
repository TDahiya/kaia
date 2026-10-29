"""
Extensible tool registry — maps tool names to executors and Claude definitions.
"""

import time
import json
from typing import Any, Callable, Awaitable
from dataclasses import dataclass, field
from app.database import get_supabase


@dataclass
class ToolDef:
    name: str
    description: str
    input_schema: dict
    executor: Callable[..., Awaitable[Any]]
    requires_confirmation: bool = False
    category: str = "general"


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDef] = {}

    def register(self, tool: ToolDef):
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDef | None:
        return self._tools.get(name)

    def list_definitions(self) -> list[dict]:
        """Return Claude-format tool definitions."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in self._tools.values()
        ]

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    async def execute(
        self, name: str, args: dict, org_id: str | None = None, conversation_id: str | None = None
    ) -> Any:
        tool = self._tools.get(name)
        if not tool:
            return {"error": f"Unknown tool: {name}"}

        start = time.monotonic()
        try:
            result = await tool.executor(**args)
            elapsed = int((time.monotonic() - start) * 1000)

            if org_id:
                _log_execution(org_id, conversation_id, name, args, result, True, elapsed)

            return result
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            error_result = {"error": str(e)}

            if org_id:
                _log_execution(org_id, conversation_id, name, args, error_result, False, elapsed)

            return error_result


def _log_execution(
    org_id: str, conversation_id: str | None, tool_name: str,
    args: dict, result: Any, success: bool, duration_ms: int
):
    try:
        db = get_supabase()
        db.table("tool_executions").insert({
            "org_id": org_id,
            "conversation_id": conversation_id,
            "tool_name": tool_name,
            "tool_args": args,
            "result": result if isinstance(result, dict) else {"value": str(result)[:1000]},
            "success": success,
            "duration_ms": duration_ms,
        }).execute()
    except Exception:
        pass  # don't fail the tool call over logging


# Global registry instance
registry = ToolRegistry()
