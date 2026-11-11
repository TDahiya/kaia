"""
AI Brain — model routing, conversation handling, tool orchestration.
Routes requests to GPT-4o-mini/GPT-4o/GPT-4.1 based on task complexity.
"""

import time
import json
from enum import Enum
from dataclasses import dataclass
from openai import OpenAI, AsyncOpenAI
from app.config import get_settings
from app.services.usage_tracker import track_llm_usage

_client: OpenAI | None = None
_async_client: AsyncOpenAI | None = None


def get_openai() -> OpenAI:
    global _client
    if _client is None:
        s = get_settings()
        if not s.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        _client = OpenAI(api_key=s.openai_api_key)
    return _client


def get_async_openai() -> AsyncOpenAI:
    global _async_client
    if _async_client is None:
        s = get_settings()
        if not s.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        _async_client = AsyncOpenAI(api_key=s.openai_api_key)
    return _async_client


class ModelTier(str, Enum):
    FAST = "fast"
    STANDARD = "standard"
    PREMIUM = "premium"


COMPLEXITY_KEYWORDS_STANDARD = {
    "plan", "analyze", "compare", "research", "summarize email",
    "draft email", "schedule", "create event", "write report",
    "multi-step", "investigate",
}
COMPLEXITY_KEYWORDS_PREMIUM = {
    "complex analysis", "strategic", "architecture", "debug deeply",
}


def classify_complexity(message: str) -> ModelTier:
    lower = message.lower()
    if len(lower) < 20 and "?" in lower:
        return ModelTier.FAST
    for kw in COMPLEXITY_KEYWORDS_PREMIUM:
        if kw in lower:
            return ModelTier.PREMIUM
    for kw in COMPLEXITY_KEYWORDS_STANDARD:
        if kw in lower:
            return ModelTier.STANDARD
    if len(lower) > 500:
        return ModelTier.STANDARD
    return ModelTier.STANDARD


def get_model_id(tier: ModelTier) -> str:
    s = get_settings()
    return {
        ModelTier.FAST: s.openai_model_fast,
        ModelTier.STANDARD: s.openai_model_standard,
        ModelTier.PREMIUM: s.openai_model_premium,
    }[tier]


# Pricing per million tokens (input, output)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1": (2.00, 8.00),
}


@dataclass
class LLMResponse:
    content: str
    model: str
    tier: ModelTier
    tokens_in: int
    tokens_out: int
    estimated_cost_usd: float
    tool_calls: list[dict] | None = None
    stop_reason: str = ""


def build_system_prompt(agent_prompt: str, memories: list[str] | None = None) -> str:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    parts = [agent_prompt]
    parts.append(f"\n\n## Current context\nToday is {now.strftime('%A, %B %d, %Y')}. Current time is {now.strftime('%H:%M')} UTC.")
    if memories:
        parts.append("\n\n## What you know about the user\n" + "\n".join(f"- {m}" for m in memories[:20]))
    return "\n".join(parts)


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    prices = MODEL_PRICING.get(model, (2.50, 10.0))
    return (tokens_in * prices[0] + tokens_out * prices[1]) / 1_000_000


def _convert_tools_for_openai(tools: list[dict]) -> list[dict]:
    """Convert Anthropic-style tool defs to OpenAI function-calling format."""
    openai_tools = []
    for t in tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            },
        })
    return openai_tools


async def chat(
    messages: list[dict],
    system_prompt: str,
    tools: list[dict] | None = None,
    tier: ModelTier | None = None,
    org_id: str | None = None,
    max_tokens: int = 4096,
) -> LLMResponse:
    if tier is None:
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        tier = classify_complexity(last_user if isinstance(last_user, str) else "")

    model = get_model_id(tier)
    client = get_openai()

    # OpenAI uses system as a message, not a parameter
    openai_messages = [{"role": "system", "content": system_prompt}]

    for m in messages:
        role = m["role"]
        content = m["content"]

        if role == "user" and isinstance(content, list):
            # Tool results from our tool loop
            for item in content:
                if item.get("type") == "tool_result":
                    openai_messages.append({
                        "role": "tool",
                        "tool_call_id": item["tool_use_id"],
                        "content": item.get("content", ""),
                    })
        elif role == "assistant" and isinstance(content, list):
            # Assistant message with tool calls
            text_parts = []
            tc_list = []
            for block in content:
                if block.get("type") == "text":
                    text_parts.append(block["text"])
                elif block.get("type") == "tool_use":
                    tc_list.append({
                        "id": block["id"],
                        "type": "function",
                        "function": {
                            "name": block["name"],
                            "arguments": json.dumps(block["input"]),
                        },
                    })
            msg: dict = {"role": "assistant", "content": "\n".join(text_parts) or None}
            if tc_list:
                msg["tool_calls"] = tc_list
            openai_messages.append(msg)
        else:
            openai_messages.append({"role": role, "content": content if isinstance(content, str) else json.dumps(content)})

    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": openai_messages,
    }
    if tools:
        kwargs["tools"] = _convert_tools_for_openai(tools)

    start = time.monotonic()
    response = client.chat.completions.create(**kwargs)
    elapsed_ms = int((time.monotonic() - start) * 1000)

    choice = response.choices[0]
    text = choice.message.content or ""
    tool_calls = []

    if choice.message.tool_calls:
        for tc in choice.message.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            tool_calls.append({
                "id": tc.id,
                "name": tc.function.name,
                "input": args,
            })

    tokens_in = response.usage.prompt_tokens if response.usage else 0
    tokens_out = response.usage.completion_tokens if response.usage else 0
    cost = estimate_cost(model, tokens_in, tokens_out)

    if org_id:
        await track_llm_usage(org_id, model, tokens_in, tokens_out, cost)

    return LLMResponse(
        content=text,
        model=model,
        tier=tier,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        estimated_cost_usd=cost,
        tool_calls=tool_calls or None,
        stop_reason=choice.finish_reason or "",
    )


async def chat_with_tools(
    messages: list[dict],
    system_prompt: str,
    tools_definitions: list[dict],
    tool_executor,  # async callable(name, args) -> result
    org_id: str | None = None,
    tier: ModelTier | None = None,
    max_turns: int | None = None,
) -> LLMResponse:
    """Run a tool loop: call OpenAI, execute tools, return final answer."""
    s = get_settings()
    max_turns = max_turns or s.max_tool_calls_per_turn
    all_tokens_in = 0
    all_tokens_out = 0
    model = get_model_id(tier or ModelTier.FAST)

    current_messages = list(messages)
    seen_tool_calls: set[str] = set()

    for turn in range(max_turns):
        resp = await chat(
            current_messages,
            system_prompt,
            tools=tools_definitions,
            tier=tier,
            org_id=org_id,
        )
        model = resp.model
        all_tokens_in += resp.tokens_in
        all_tokens_out += resp.tokens_out

        if resp.stop_reason != "tool_calls" or not resp.tool_calls:
            resp.tokens_in = all_tokens_in
            resp.tokens_out = all_tokens_out
            resp.estimated_cost_usd = estimate_cost(model, all_tokens_in, all_tokens_out)
            return resp

        # Build assistant message with tool calls (OpenAI format internally)
        assistant_content = []
        if resp.content:
            assistant_content.append({"type": "text", "text": resp.content})
        for tc in resp.tool_calls:
            assistant_content.append({
                "type": "tool_use",
                "id": tc["id"],
                "name": tc["name"],
                "input": tc["input"],
            })
        current_messages.append({"role": "assistant", "content": assistant_content})

        # Execute tools and collect results
        tool_results = []
        for tc in resp.tool_calls:
            call_sig = f"{tc['name']}:{json.dumps(tc['input'], sort_keys=True)}"
            if call_sig in seen_tool_calls:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    "content": "Error: This exact tool call was already made. Provide your final answer.",
                    "is_error": True,
                })
                continue
            seen_tool_calls.add(call_sig)

            try:
                result = await tool_executor(tc["name"], tc["input"])
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    "content": json.dumps(result) if not isinstance(result, str) else result,
                })
            except Exception as e:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    "content": f"Error: {e}",
                    "is_error": True,
                })

        current_messages.append({"role": "user", "content": tool_results})

    # Hit max turns
    current_messages.append({
        "role": "user",
        "content": "You've reached the maximum number of tool calls. Please provide your final answer now.",
    })
    resp = await chat(current_messages, system_prompt, tier=tier, org_id=org_id)
    resp.tokens_in = all_tokens_in + resp.tokens_in
    resp.tokens_out = all_tokens_out + resp.tokens_out
    resp.estimated_cost_usd = estimate_cost(model, resp.tokens_in, resp.tokens_out)
    return resp
