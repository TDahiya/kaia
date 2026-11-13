"""Health check and system status."""

from fastapi import APIRouter, Depends
from app.config import get_settings
from app.auth import require_owner
from app.services import app_settings

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health():
    return {"status": "ok", "service": "kaia-backend"}


@router.get("/system-status")
async def system_status(user: dict = Depends(require_owner)):
    s = get_settings()

    def check(val: str) -> str:
        return "configured" if val else "not_configured"

    return {
        "supabase": check(s.supabase_url),
        "openai": check(s.openai_api_key),
        "deepgram": check(s.deepgram_api_key),
        "google_oauth": check(s.google_client_id),
        "twilio": check(s.twilio_account_sid),
        "twilio_phone": check(s.twilio_phone_number),
        "owner_phone": check(app_settings.get_owner_phone()),
        "encryption": check(s.token_encryption_key),
        "weather": check(s.google_maps_api_key),
        "maps": check(s.google_maps_api_key),
        "models": {
            "fast": s.openai_model_fast,
            "standard": s.openai_model_standard,
            "premium": s.openai_model_premium,
        },
        "limits": {
            "monthly_spend_usd": s.monthly_spend_limit_usd,
            "max_tool_calls_per_turn": s.max_tool_calls_per_turn,
            "max_audio_session_seconds": s.max_audio_session_seconds,
            "max_call_duration_seconds": s.max_call_duration_seconds,
        },
    }
