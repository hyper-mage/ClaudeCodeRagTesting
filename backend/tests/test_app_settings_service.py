"""Phase 11 gap-closure (11-06) — is_langsmith_enabled unit coverage.

The runtime LangSmith master toggle reads a GLOBAL app_settings row
(key='langsmith_enabled') once per chat turn through a module-level ~15s TTL
cache, so the owner can flip tracing live via one SQL UPDATE — no backend
restart. The reader must NEVER raise and must default to True (default-on) on
a missing row or any read error: that default is SAFE because chat.py composes
the gate as `enabled = False if (is_user_key or not langsmith_on) else None`,
so a BYOK turn stays untraced regardless of the flag read outcome (SEC-01
invariant — covered end-to-end in test_langsmith_runtime_toggle.py).

Unit-level, offline: the db is a MagicMock mirroring the supabase-py chain
`db.table(...).select(...).eq(...).maybe_single().execute()` — no real
Supabase. Every test resets the module TTL cache first so state never leaks
between tests; TTL expiry is driven deterministically (aging the cached
timestamp), never by sleeping.
"""
from unittest.mock import MagicMock

import pytest

from services import app_settings_service
from services.app_settings_service import is_langsmith_enabled


def _make_db(data):
    """Build a MagicMock db whose read chain returns a result with .data=data.

    Returns (db, execute_mock, result) so tests can count DB reads and flip
    the underlying row between calls (the live-flip simulation).
    """
    db = MagicMock()
    result = MagicMock()
    result.data = data
    execute_mock = (
        db.table.return_value
        .select.return_value
        .eq.return_value
        .maybe_single.return_value
        .execute
    )
    execute_mock.return_value = result
    return db, execute_mock, result


@pytest.fixture(autouse=True)
def _fresh_cache():
    """Reset the module TTL cache before AND after every test (no state leaks)."""
    app_settings_service._reset_cache()
    yield
    app_settings_service._reset_cache()


def test_returns_true_when_row_true():
    """A langsmith_enabled row with jsonb true reads back as True."""
    db, _, _ = _make_db({"value": True})
    assert is_langsmith_enabled(db) is True


def test_returns_false_when_row_false():
    """A langsmith_enabled row with jsonb false reads back as False (kill-switch)."""
    db, _, _ = _make_db({"value": False})
    assert is_langsmith_enabled(db) is False


def test_missing_row_defaults_true():
    """Empty/None data (row absent) => True — default-on, never a crash."""
    db, _, _ = _make_db(None)
    assert is_langsmith_enabled(db) is True


def test_missing_row_empty_list_defaults_true():
    """Defensive: a list-shaped empty payload also means 'no row' => True."""
    db, _, _ = _make_db([])
    assert is_langsmith_enabled(db) is True


def test_db_exception_defaults_true():
    """A read exception with NO prior successful read => True, never propagates.

    Security-invariant support (T-11-06-04): a broken flag read may only ever
    (re)enable NON-BYOK tracing; it must not take down the chat turn. (With a
    prior successful read the error path keeps the cached value instead --
    see test_db_exception_keeps_last_known_false.)
    """
    db = MagicMock()
    (
        db.table.return_value
        .select.return_value
        .eq.return_value
        .maybe_single.return_value
        .execute
    ).side_effect = RuntimeError("db down")
    assert is_langsmith_enabled(db) is True  # must not raise


def test_db_exception_keeps_last_known_false():
    """Stale-while-error (WR-01): a transient refresh error must NOT revert a
    known-good OFF back to ON for the next TTL window.

    Last successful read cached False (owner kill-switch OFF); the TTL then
    expires and the refresh read raises -> the reader keeps False, preserving
    the owner's most recent explicit decision. The failure still refreshes the
    cache stamp, so a failing DB is read at most once per TTL window.
    """
    db, execute_mock, _ = _make_db({"value": False})
    assert is_langsmith_enabled(db) is False
    assert execute_mock.call_count == 1

    # Age the cache past the TTL, then make the refresh read fail.
    assert app_settings_service._cached_at is not None
    app_settings_service._cached_at -= app_settings_service._TTL_SECONDS + 1
    execute_mock.side_effect = RuntimeError("transient db blip")

    assert is_langsmith_enabled(db) is False  # stale-while-error keeps OFF
    assert execute_mock.call_count == 2
    # The failed refresh re-stamped the cache: the next call inside the TTL
    # window hits the cache (no third DB read -- the failing DB isn't hammered).
    assert is_langsmith_enabled(db) is False
    assert execute_mock.call_count == 2


@pytest.mark.parametrize(
    "raw,expected",
    [
        (True, True),
        (False, False),
        ("true", True),
        ("false", False),
        ("TRUE", True),
        ("False", False),
        (1, True),
        (0, False),
    ],
)
def test_jsonb_coercion(raw, expected):
    """jsonb values delivered as bool/str/int all coerce defensively."""
    db, _, _ = _make_db({"value": raw})
    assert is_langsmith_enabled(db) is expected


def test_ttl_cache_hits_then_expires():
    """Within the TTL the db is read at most once; past it, the read repeats.

    Expiry is driven deterministically by aging the cached timestamp — no
    sleeping. After expiry the FLIPPED row value is returned, proving a SQL
    flip goes live within one TTL window with no restart.
    """
    db, execute_mock, result = _make_db({"value": False})

    # Two calls inside the TTL window => exactly one DB read.
    assert is_langsmith_enabled(db) is False
    assert is_langsmith_enabled(db) is False
    assert execute_mock.call_count == 1

    # Flip the row, then age the cached timestamp past the TTL.
    result.data = {"value": True}
    assert app_settings_service._cached_at is not None
    app_settings_service._cached_at -= app_settings_service._TTL_SECONDS + 1

    # Next call re-reads the db (count increments) and sees the flipped value.
    assert is_langsmith_enabled(db) is True
    assert execute_mock.call_count == 2
