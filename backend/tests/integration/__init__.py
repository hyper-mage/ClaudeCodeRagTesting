"""Real-DB integration smoke tests for DB-shape backend endpoints (quick task 260718-o4c).

These tests DELIBERATELY do NOT mock `get_supabase`. They perform real PostgREST
round-trips against the `.env` dev Supabase project so that PostgREST-shape regressions
(e.g. the `get_thread` `maybe_single()` + `*, messages(*)` resource-embedding APIError-204
bug) are caught by `pytest` before deploy — a mocked test passed green while that exact
code was runtime-broken.

  > WARNING: this suite MUTATES the dev Supabase project. It CREATEs and DELETEs throwaway
  > rows (thread, messages, folder, document). Mitigations: all rows are sentinel-prefixed
  > (`__inttest_260718__`, greppable/deletable), use fresh UUIDs per run, are owned by the
  > never-login system user, and are removed by teardown-after-yield (runs even on assertion
  > failure). The skip-guard below makes the whole suite a no-op when creds are absent.

Marker note: the `integration` marker is already registered in `backend/pytest.ini` under
`--strict-markers`, so NO ini change is required to tag these tests.

Run command (REQUIRED for this project — venv interpreter + `-p no:dash`):
  backend/venv/Scripts/python.exe -m pytest backend/tests/integration -p no:dash -q
"""
import pytest

from config import get_settings

# Sentinel prefix stamped on every row this suite creates, so orphans (if teardown were
# ever skipped) are trivially greppable/deletable in the dev DB.
SENTINEL = "__inttest_260718__"

# The system user is a REAL `auth.users` row seeded by migration
# 20240301000017_create_system_user.sql. It satisfies the `user_id NOT NULL REFERENCES
# auth.users(id)` FK on threads/messages/folders/documents WITHOUT any Supabase admin API,
# is deterministic and guaranteed present, and NEVER logs in via the frontend — so rows we
# own under it are never visible to a real logged-in user.
SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000000"

# Skip guard: the suite only runs when dev Supabase creds resolve. Absent creds (hermetic
# CI, a contributor without `.env`) → every test SKIPS (not errors).
HAS_SUPABASE = bool(
    get_settings().supabase_url_resolved and get_settings().supabase_service_role_key
)

requires_supabase = pytest.mark.skipif(
    not HAS_SUPABASE,
    reason="integration: dev Supabase creds absent",
)
