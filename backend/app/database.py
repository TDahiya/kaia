from supabase import create_client, Client
from app.config import get_settings

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        s = get_settings()
        if not s.supabase_url or not s.supabase_service_role_key:
            raise RuntimeError("Supabase not configured — set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
        _client = create_client(s.supabase_url, s.supabase_service_role_key)
    return _client


def get_supabase_anon() -> Client:
    s = get_settings()
    if not s.supabase_url or not s.supabase_anon_key:
        raise RuntimeError("Supabase not configured")
    return create_client(s.supabase_url, s.supabase_anon_key)
