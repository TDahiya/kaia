"""
AI Brain — model routing, conversation handling, tool orchestration.
Routes requests to Haiku/Sonnet/Opus based on task complexity.
"""

import time
import json
import anthropic
from enum import Enum
from dataclasses import dataclass
from app.config import get_settings
from app.services.usage_tracker import track_llm_usage

_client: anthropic.Anthropic | None = None


def get_anthropic() -> anthropic.Anthropic:
    global _client
    if _client is None:
        s = get_settings()
        if not s.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        _client = anthropic.Anthropic(api_key=s.anthropic_api_key)
    return _client


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
    return ModelTier.FAST


def get_model_id(tier: ModelTier) -> str:
    s = get_settings()
    return {
        ModelTier.FAST: s.claude_model_fast,
        ModelTier.STANDARD: s.claude_model_standard,
        ModelTier.PREMIUM: s.claude_model_premium,
    }[tier]


# Pricing per million tokens (input, output) as of Oct 2026
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
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
    parts = [agent_prompt]
    if memories:
        parts.append("\n\n## What you know about the user\n" + "\n".join(f"- {m}" for m in memories[:20]))
    return "\n".join(parts)


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    prices = MODEL_PRICING.get(model, (2.0, 10.0))
    return (tokens_in * prices[0] + tokens_out * prices[1]) / 1_000_000


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
    client = get_anthropic()

    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools

    start = time.monotonic()
    response = client.messages.create(**kwargs)
    elapsed_ms = int((time.monotonic() - start) * 1000)

    text_parts = []
    tool_calls = []
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use":
            tool_calls.append({
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })

    tokens_in = response.usage.input_tokens
    tokens_out = response.usage.output_tokens
    cost = estimate_cost(model, tokens_in, tokens_out)

    if org_id:
        await track_llm_usage(org_id, model, tokens_in, tokens_out, cost)

    return LLMResponse(
        content="\n".join(text_parts),
        model=model,
        tier=tier,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        estimated_cost_usd=cost,
        tool_calls=tool_calls or None,
        stop_reason=response.stop_reason,
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
    """Run a tool loop: call Claude, execute tools, return final answer."""
    s = get_settings()
    max_turns = max_turns or s.max_tool_calls_per_turn
    all_tokens_in = 0
    all_tokens_out = 0
    model = get_model_id(tier or ModelTier.FAST)

    current_messages = list(messages)
    seen_tool_calls: set[str] = set()  # loop detection

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

        if resp.stop_reason != "tool_use" or not resp.tool_calls:
            resp.tokens_in = all_tokens_in
            resp.tokens_out = all_tokens_out
            resp.estimated_cost_usd = estimate_cost(model, all_tokens_in, all_tokens_out)
            return resp

        # Build assistant message with all content blocks
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

    # Hit max turns — ask for final answer
    current_messages.append({
        "role": "user",
        "content": "You've reached the maximum number of tool calls. Please provide your final answer now.",
    })
    resp = await chat(current_messages, system_prompt, tier=tier, org_id=org_id)
    resp.tokens_in = all_tokens_in + resp.tokens_in
    resp.tokens_out = all_tokens_out + resp.tokens_out
    resp.estimated_cost_usd = estimate_cost(model, resp.tokens_in, resp.tokens_out)
    return resp
