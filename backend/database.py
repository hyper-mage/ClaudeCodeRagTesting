from supabase import create_client, Client
from config import get_settings

# Lazy module-level singleton (mirrors get_settings()). The service-role client is the
# shared, stateless server-side client — it bypasses RLS by design and mutates no
# per-request state, so a single instance is safe across FastAPI's threadpool
# (supabase-py wraps a thread-safe httpx.Client). Building one client per request was
# pure overhead on the ChatPage mount fan-out.
#
# TESTS: each router patches the imported name in its own module
# (`routers.<x>.get_supabase`) and `main.get_supabase`, so tests replace the whole
# function and never touch this cache — the singleton does not break them.
_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        settings = get_settings()
        _client = create_client(
            settings.supabase_url_resolved, settings.supabase_service_role_key
        )
    return _client
