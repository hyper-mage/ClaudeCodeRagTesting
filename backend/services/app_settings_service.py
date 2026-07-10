"""Global app_settings flag reads (Phase 11-06, SEC-01 runtime LangSmith toggle).

Exposes is_langsmith_enabled(db) -> bool: a TTL-cached read of the GLOBAL
app_settings row key='langsmith_enabled' via the passed service-role client.
The owner flips the flag live with one SQL UPDATE in the Supabase SQL editor;
the change goes live on every backend instance within the ~15s cache window --
no restart, no admin UI.

Fail-safe contract (T-11-06-04): a missing row returns True (default-on); a
read ERROR keeps the last successfully-read value (stale-while-error, True
only when no read has ever succeeded) so a transient DB blip cannot silently
revert an owner's OFF flip back to ON; and the reader NEVER raises.
Default-on is deliberately SAFE for SEC-01 because chat.py composes the gate
as `enabled = False if (is_user_key or not langsmith_on) else None` -- the
locally-resolved BYOK term forces suppression for a user-key turn regardless
of this read's outcome; a broken flag read can only ever (re)enable NON-BYOK
tracing. Default-off would instead silently kill owner observability on a
transient DB blip.
"""
import logging
import time

logger = logging.getLogger(__name__)

# Runtime-flip latency bound: a SQL flip on app_settings goes live within this
# window. Module constant, deliberately NOT env-driven -- there is no per-deploy
# reason to tune it, and config drift here would only obscure the flip latency.
_TTL_SECONDS = 15

# Module-level TTL cache (NOT @lru_cache -- the read must be time-bounded so a
# flip goes live without a restart). _cached_at is a time.monotonic() stamp;
# None means "no read yet". Also bounds per-turn DB load to at most one read
# per TTL window (T-11-06-03).
_cached_value: bool = True
_cached_at: float | None = None


def _coerce_bool(value) -> bool:
    """Coerce a jsonb-delivered value to bool defensively.

    Accepts Python bool, the strings "true"/"false" (case-insensitive), and
    numeric 0/1. Anything unrecognized falls back to True, matching the
    module's default-on fail-safe.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "false":
            return False
        if lowered == "true":
            return True
        return True  # unrecognized string -> default-on
    if isinstance(value, (int, float)):
        return bool(value)
    return True  # unrecognized type -> default-on


def _reset_cache() -> None:
    """Test hook: clear the TTL cache so the next call re-reads the DB."""
    global _cached_value, _cached_at
    _cached_value = True
    _cached_at = None


def is_langsmith_enabled(db) -> bool:
    """Return the global LangSmith master-toggle flag (default-on, never raises).

    Reads app_settings key='langsmith_enabled' through the passed service-role
    client, cached for _TTL_SECONDS so the per-turn call costs at most one DB
    read per window. Missing row -> True (default-on); read error -> the last
    successfully-cached value (stale-while-error; True when nothing was ever
    read). The caller's gate forces False for any BYOK turn, keeping user-key
    turns untraced no matter what this returns (SEC-01 invariant).
    """
    global _cached_value, _cached_at
    now = time.monotonic()
    if _cached_at is not None and (now - _cached_at) < _TTL_SECONDS:
        return _cached_value

    try:
        row = (
            db.table("app_settings")
            .select("value")
            .eq("key", "langsmith_enabled")
            .maybe_single()
            .execute()
        )
        # Empty-row guard (mirrors chat.py's maybe_single usage): .data is a
        # dict when the row exists; None/list/anything else means "no row".
        if row and isinstance(row.data, dict) and "value" in row.data:
            value = _coerce_bool(row.data["value"])
        else:
            value = True  # row missing -> default-on
    except Exception as e:
        # Never propagate -- a broken flag read must not take down the chat
        # turn, and default-on cannot leak a BYOK turn (see module docstring).
        # Stale-while-error (WR-01): keep the LAST successfully-read value so
        # a transient DB blip at TTL refresh cannot silently revert an owner's
        # OFF flip back to ON; default to True only when there has never been
        # a read (_cached_at is None). The stamp refresh below still applies,
        # so a failing DB is retried at most once per TTL window.
        logger.warning(
            f"app_settings langsmith_enabled read failed; keeping last value: {e}"
        )
        value = _cached_value if _cached_at is not None else True

    _cached_value = value
    _cached_at = now
    return value
