from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    anthropic_api_key: str = ""
    claude_model_fast: str = "claude-haiku-5-5"
    claude_model_standard: str = "claude-sonnet-5-5"
    claude_model_premium: str = "claude-opus-5-5"

    deepgram_api_key: str = ""

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    google_sheets_spreadsheet_id: str = ""
    google_memory_doc_id: str = ""

    telnyx_api_key: str = ""
    telnyx_phone_number: str = ""
    telnyx_connection_id: str = ""
    telnyx_webhook_secret: str = ""

    owner_phone_e164: str = ""

    app_base_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"
    token_encryption_key: str = ""
    jwt_secret: str = "change-me"

    openweather_api_key: str = ""

    monthly_spend_limit_usd: float = 50.0
    max_tool_calls_per_turn: int = 15
    max_audio_session_seconds: int = 600
    max_call_duration_seconds: int = 300
    daily_outbound_call_limit: int = 5

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
