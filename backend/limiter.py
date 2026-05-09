"""Rate limiter for /api/chat (SEC-04).

Lives in its own module to AVOID a circular import between
`main.py` (which needs the limiter for app.state + exception handler)
and `routers/chat.py` (which needs it for the @limiter.limit decorator).

Per Phase 6 D-01..D-05:
  - Library: slowapi==0.1.9
  - Storage: in-memory (single Fly machine, suspend/resume preserves counters)
  - Scope: /api/chat only (decorated at the route)
  - Key: Supabase user_id from request.state (set by auth.get_user_id)
  - Default cap: from Settings.chat_rate_limit ("20/minute")
"""
from fastapi import Request
from slowapi import Limiter


def user_id_key(request: Request) -> str:
    """slowapi key_func: rate limit per Supabase user_id.

    FastAPI resolves the auth dependency BEFORE slowapi invokes this
    function (per-route-decorator order), so request.state.user_id
    will already be set on the success path.

    Falls back to 'anonymous' if state.user_id is unset — that path
    is hit only when the auth dep would have raised 401, in which
    case the route body never runs anyway. The fallback exists purely
    to avoid a crash inside the limiter wrapper.
    """
    return getattr(request.state, "user_id", None) or "anonymous"


limiter = Limiter(key_func=user_id_key, storage_uri="memory://")
