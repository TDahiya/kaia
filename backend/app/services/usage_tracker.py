"""Usage tracking — records every API call for cost monitoring."""

from datetime import datetime, timedelta, timezone
from app.database import get_supabase
from app.config import get_settings


async def track_llm_usage(
    org_id: str, model: str, tokens_in: int, tokens_out: int, cost_usd: float
):
    db = get_supabase()
    db.table("usage_events").insert({
        "org_id": org_id,
        "provider": "openai",
        "event_type": "chat_completion",
        "quantity": tokens_in + tokens_out,
        "unit": "tokens",
        "estimated_cost_usd": float(cost_usd),
        "model": model,
        "metadata": {"tokens_in": tokens_in, "tokens_out": tokens_out},
    }).execute()


async def track_stt_usage(org_id: str, duration_seconds: float):
    cost = duration_seconds / 60 * 0.0043  # Nova-3 streaming
    db = get_supabase()
    db.table("usage_events").insert({
        "org_id": org_id,
        "provider": "deepgram_stt",
        "event_type": "transcription",
        "quantity": duration_seconds,
        "unit": "seconds",
        "estimated_cost_usd": float(cost),
    }).execute()


async def track_tts_usage(org_id: str, characters: int):
    cost = characters / 1000 * 0.007  # Aura 2
    db = get_supabase()
    db.table("usage_events").insert({
        "org_id": org_id,
        "provider": "deepgram_tts",
        "event_type": "synthesis",
        "quantity": characters,
        "unit": "characters",
        "estimated_cost_usd": float(cost),
    }).execute()


async def track_telephony_usage(org_id: str, duration_seconds: int, direction: str):
    rate = 0.02 if direction == "inbound" else 0.10  # conservative estimate
    cost = duration_seconds / 60 * rate
    db = get_supabase()
    db.table("usage_events").insert({
        "org_id": org_id,
        "provider": "telnyx",
        "event_type": f"call_{direction}",
        "quantity": duration_seconds,
        "unit": "seconds",
        "estimated_cost_usd": float(cost),
    }).execute()


async def get_monthly_spend(org_id: str) -> dict:
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    db = get_supabase()
    result = db.table("usage_events") \
        .select("provider, estimated_cost_usd") \
        .eq("org_id", org_id) \
        .gte("created_at", month_start.isoformat()) \
        .execute()

    by_provider: dict[str, float] = {}
    total = 0.0
    for row in result.data:
        p = row["provider"]
        c = float(row["estimated_cost_usd"])
        by_provider[p] = by_provider.get(p, 0) + c
        total += c

    return {
        "total_usd": round(total, 4),
        "by_provider": {k: round(v, 4) for k, v in by_provider.items()},
        "limit_usd": get_settings().monthly_spend_limit_usd,
        "remaining_usd": round(get_settings().monthly_spend_limit_usd - total, 4),
    }


async def check_spend_limit(org_id: str) -> bool:
    """Returns True if under limit, False if limit reached."""
    spend = await get_monthly_spend(org_id)
    return spend["remaining_usd"] > 0
