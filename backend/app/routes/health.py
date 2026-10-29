"""Health check and system status."""

from fastapi import APIRouter, Depends
from app.config import get_settings
from app.auth import get_current_user

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health():
    return {"status": "ok", "service": "kaia-backend"}


@router.get("/system-status")
async def system_status(user: dict = Depends(get_current_user)):
    s = get_settings()

    def check(val: str) -> str:
        return "configured" if val else "not_configured"

    return {
        "supabase": check(s.supabase_url),
        "anthropic": check(s.anthropic_api_key),
        "deepgram": check(s.deepgram_api_key),
        "google_oauth": check(s.google_client_id),
        "telnyx": check(s.telnyx_api_key),
        "telnyx_phone": check(s.telnyx_phone_number),
        "owner_phone": check(s.owner_phone_e164),
        "encryption": check(s.token_encryption_key),
        "weather": check(s.openweather_api_key),
        "models": {
            "fast": s.claude_model_fast,
            "standard": s.claude_model_standard,
            "premium": s.claude_model_premium,
        },
        "limits": {
            "monthly_spend_usd": s.monthly_spend_limit_usd,
            "max_tool_calls_per_turn": s.max_tool_calls_per_turn,
            "max_audio_session_seconds": s.max_audio_session_seconds,
            "max_call_duration_seconds": s.max_call_duration_seconds,
        },
    }
