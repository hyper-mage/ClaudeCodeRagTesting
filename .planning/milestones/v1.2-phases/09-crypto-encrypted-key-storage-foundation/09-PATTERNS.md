# Phase 9: Crypto + Encrypted Key Storage Foundation - Pattern Map

**Mapped:** 2026-06-18
**Files analyzed:** 7 (3 new code, 1 modified code, 2 new + 1 modified migration, 3 new/modified test files)
**Analogs found:** 7 / 7 (every new/modified file has a strong in-repo analog — this is an additive, composition-only phase)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/services/crypto_service.py` (NEW) | service (crypto) | transform (in-memory encrypt/decrypt) | `backend/services/web_search_service.py` (module shape) + `backend/auth.py` (`cryptography` usage) | role-match |
| `backend/config.py` (MODIFY) | config | request-response (settings load) | `backend/config.py` itself (existing secret fields) | exact (self) |
| `supabase/migrations/20240301000025_create_user_api_keys.sql` (NEW) | migration (table + RLS) | CRUD (table create) | `20240301000018_create_folders_table.sql` (table+RLS) + `20240301000020_update_rls_policies.sql` (own-row policy) | role-match (composite) |
| `supabase/migrations/20240301000026_harden_sql_tool_allowlist.sql` (NEW, or fold into 025) | migration (RPC redefine) | transform (SECURITY DEFINER fn) | `20240301000015_execute_readonly_query.sql` (the RPC being hardened) | exact (redefine of analog) |
| `backend/tests/test_crypto_service.py` (NEW) | test (unit) | transform round-trip | `backend/tests/test_config.py` (env+cache_clear) + RESEARCH §Code Examples | role-match |
| `backend/tests/test_config.py` (MODIFY) | test (unit) | request-response | `backend/tests/test_config.py` itself (`chat_max_iterations` pair) | exact (self) |
| `backend/tests/test_sql_keys_lockdown.py` (NEW) | test (unit, SEC probe) | CRUD probe via RPC | `backend/tests/test_folders_api.py` (`patch(get_supabase)` + MagicMock chain) | role-match |

## Pattern Assignments

### `backend/services/crypto_service.py` (service, transform) — NEW

**Analogs:** `backend/services/web_search_service.py` (service module shape, `get_settings()` access, `_private` helper naming), `backend/auth.py` (confirms `cryptography` dep present + module-level singleton convention).

**Module/import + settings-access pattern** — mirror `web_search_service.py` lines 1-13 (`from config import get_settings`, `settings = get_settings()` inside the function, NOT at import time so tests can `cache_clear`):
```python
# web_search_service.py:1-12 (the shape to copy)
import httpx
import logging
from config import get_settings

logger = logging.getLogger(__name__)

def search_web(query: str) -> dict:
    """..."""
    settings = get_settings()
    ...
```

**Private-helper naming** — `web_search_service.py` uses `_search_tavily(...)`; `parsing_service.py` uses `_get_converter()`. Follow the `_underscore` prefix for `_multifernet()`. (CLAUDE.md Conventions: "Private helpers prefixed with underscore".)

**`cryptography` is already a dependency** — `backend/auth.py` line 1 imports `jwt` (PyJWT, backed by `cryptography` for ES256). RESEARCH confirms `cryptography==46.0.5` is pinned. Import surface for this file:
```python
from cryptography.fernet import Fernet, MultiFernet
from config import get_settings
```

**Core pattern (VERIFIED in RESEARCH §Pattern 1 against installed 46.0.5)** — parse `KEY_ENCRYPTION_SECRET` as comma-separated, new-key-first; encrypt with primary, decrypt tries all, `.rotate()` re-encrypts:
```python
def _multifernet() -> MultiFernet:
    keys = [k.strip() for k in get_settings().key_encryption_secret.split(",") if k.strip()]
    return MultiFernet([Fernet(k.encode()) for k in keys])

def encrypt_key(plaintext: str) -> str:
    return _multifernet().encrypt(plaintext.encode()).decode()

def decrypt_key(ciphertext: str) -> str:
    return _multifernet().decrypt(ciphertext.encode()).decode()

def rotate_token(ciphertext: str) -> str:
    return _multifernet().rotate(ciphertext.encode()).decode()
```
> Function signatures are Claude's discretion (CONTEXT D-40), but the names `encrypt_key`/`decrypt_key`/`rotate_token` are used by the RESEARCH test examples and Phase 10/11 consumers — keep the API minimal and stable (CONTEXT integration note line 84).

**Function-design conventions to follow** (CLAUDE.md): type hints on all params/returns; `str | None` union (not `Optional`); 4-space indent; double quotes; docstrings on public functions. `KEY_ENCRYPTION_SECRET` must NEVER be logged/traced/returned (D-04) — do not add a `logger.info` that echoes keys or plaintext.

---

### `backend/config.py` (config) — MODIFY

**Analog:** the file itself — add `key_encryption_secret` exactly like the existing empty-default secret fields.

**Existing secret-field pattern** (`config.py` lines 13-17 — empty-string default, snake_case attr, auto-mapped from UPPER_SNAKE env var by pydantic-settings):
```python
class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""
    openai_api_key: str = ""
    langsmith_api_key: str = ""
```

**Where to add** — alongside the other secrets near the top of `Settings`, with an explanatory comment matching the file's style (see the `chat_rate_limit` comment at line 24-25):
```python
    # BYOK master key (Phase 9 D-04) — comma-separated url-safe base64 Fernet keys,
    # NEW KEY FIRST for MultiFernet rotation. Distinct value per env (.env vs .env.prod).
    key_encryption_secret: str = ""
```

**`@lru_cache` + `ENV_FILE` already wired** — `config.py` lines 8-9 (`ENV_FILE` override) and 143-145 (`@lru_cache def get_settings()`). No change needed; this is what makes D-03/D-04 dual-env work and what tests must `cache_clear()` against.

---

### `supabase/migrations/20240301000025_create_user_api_keys.sql` (migration: table + RLS + REVOKE) — NEW

**Analogs:** `20240301000018_create_folders_table.sql` (CREATE TABLE + `auth.users(id)` FK + `ENABLE ROW LEVEL SECURITY` + 4-policy block + header comment) and `20240301000020_update_rls_policies.sql` (the `auth.uid() = user_id` own-row policy wording).

**Next free number is `...025`** — verified: last migration is `20240301000024_add_tools_used_to_messages.sql`. Each migration runs as one transaction (CONTEXT line 78).

**Header-comment + CREATE TABLE + FK + RLS-enable pattern** (copy structure from `018_create_folders_table.sql` lines 1-25):
```sql
-- folders ... header explains purpose + RLS intent + Depends-on
CREATE TABLE folders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id),
  ...
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE folders ENABLE ROW LEVEL SECURITY;
```
> For `user_api_keys` the PK is `user_id` itself (one key per user — CONTEXT "carried forward", line 36): `user_id uuid primary key references auth.users(id) on delete cascade`. Ciphertext-only column + `key_version integer not null default 1` (D-02). Proposed schema in RESEARCH §Pattern 2 lines 200-208.

**Own-row RLS policy wording** — `user_api_keys` is own-row ONLY (NO `visibility = 'public'` clause; the keys table is never public). Take the `auth.uid() = user_id` form from migration 020 but DROP the `OR visibility = 'public'` part. Compare:
```sql
-- 020 (mixed-visibility, DO NOT copy the public clause for keys):
CREATE POLICY "Users can view own or public documents"
  ON documents FOR SELECT USING (auth.uid() = user_id OR visibility = 'public');
CREATE POLICY "Users can insert own documents"
  ON documents FOR INSERT WITH CHECK (auth.uid() = user_id);
```
For `user_api_keys`, all four (SELECT/INSERT/UPDATE/DELETE) gate on plain `auth.uid() = user_id` (own-row, no public; CONTEXT line 79). INSERT uses `WITH CHECK`, SELECT/UPDATE/DELETE use `USING`.

**SEC-02 GATE 1 — the REVOKE (new, no analog elsewhere in the repo)** — must live in the migration file, NOT issued through the RPC (the RPC keyword-blocks `revoke`, see migration 015 line 26):
```sql
-- SEC-02 GATE 1 (D-01): privilege is checked BEFORE RLS, so this denies the
-- SQL-tool ('authenticated') read path entirely. Service-role backend is unaffected.
revoke select on user_api_keys from authenticated;
```

---

### `supabase/migrations/20240301000026_harden_sql_tool_allowlist.sql` (migration: RPC redefine) — NEW (or fold into 025)

**Analog:** `20240301000015_execute_readonly_query.sql` — this IS the function being hardened. Use `CREATE OR REPLACE FUNCTION execute_readonly_query(...)` redefining the whole body, preserving every existing gate.

**Existing gates to PRESERVE verbatim** (migration 015):
- `SECURITY DEFINER` + `LANGUAGE plpgsql` (lines 9-12)
- Gate: SELECT/WITH-only — `IF NOT (lower(sanitized) ~ '^(select|with)\s')` (lines 20-23)
- Gate: keyword block incl. `grant|revoke` — line 26
- RLS context: `PERFORM set_config('request.jwt.claim.sub', calling_user_id::text, true); SET LOCAL role = 'authenticated';` (lines 30-32) ← this is the line the REVOKE applies against
- Subquery-wrap + row limit: `EXECUTE format('... FROM (%s) sub LIMIT %s ...', sanitized, max_rows)` (lines 35-39)
- `RESET role;` + `RETURN result;` (lines 42-44)

**NEW — FROM-table allowlist (SEC-02 GATE 2, D-01)** — insert AFTER the keyword block (line 28) and BEFORE the `SET LOCAL role` (line 30). Must inspect the inner `sanitized` SQL, not the wrapper. Default-deny positive allowlist:
```sql
-- after the keyword block, before SET LOCAL role:
DECLARE tbl TEXT;
BEGIN
  FOR tbl IN
    SELECT lower((regexp_matches(sanitized, '(?:from|join)\s+["]?([a-z_][a-z0-9_]*)', 'gi'))[1])
  LOOP
    IF tbl NOT IN ('threads', 'messages', 'documents', 'document_chunks') THEN
      RAISE EXCEPTION 'Query references a non-allowlisted table: %', tbl;
    END IF;
  END LOOP;
END;
```
> **RECONCILED ALLOWLIST (CONTEXT D-01, line 20-21 + Specifics line 91):** the allowlist is `{threads, messages, documents, document_chunks}` — matching `QUERYABLE_SCHEMA` in `backend/services/sql_service.py` lines 8-41 EXACTLY. The RESEARCH-era `{documents, document_chunks, folders}` is SUPERSEDED — do NOT use it. `folders` is intentionally excluded (navigated via KB tree/grep/glob tools, not Text-to-SQL); `threads`/`messages` are kept (legitimate "how many conversations?" queries). Security intent (exclude `user_api_keys`) is unchanged. RESEARCH Open Question 1 is now resolved by this decision.
> Exact regex / CTE-alias handling is the executor's discretion (RESEARCH Pitfall 4). Keep a regression test of real `documents`/`document_chunks`/`threads`/`messages` queries that must still pass.

---

### `backend/tests/test_crypto_service.py` (test, unit) — NEW

**Analog:** `backend/tests/test_config.py` (env-var + `Settings` import pattern) plus the verified examples in RESEARCH §Code Examples (lines 318-349).

**Critical fixture wiring — `@lru_cache` cache_clear** (`config.py` line 143). Tests that set `KEY_ENCRYPTION_SECRET` via `monkeypatch.setenv` MUST call `get_settings.cache_clear()` because `crypto_service` reads via `get_settings()` (not `Settings()` directly):
```python
from cryptography.fernet import Fernet

def test_encrypt_decrypt_roundtrip(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("KEY_ENCRYPTION_SECRET", key)
    from config import get_settings; get_settings.cache_clear()
    from services import crypto_service
    ct = crypto_service.encrypt_key("sk-or-v1-example")
    assert ct != "sk-or-v1-example"
    assert crypto_service.decrypt_key(ct) == "sk-or-v1-example"
```
> Rotation test (RESEARCH lines 333-347): set `KEY_ENCRYPTION_SECRET=old`, encrypt; set to `f"{new},{old}"` + `cache_clear()`, `rotate_token`; set to `new` + `cache_clear()`, assert decrypt succeeds. No shared fixture needed — tests self-generate keys (RESEARCH Wave 0 Gaps line 461).

**sys.path note** — `conftest.py` lines 2-4 already insert `backend/` on `sys.path`, so `from config import ...` / `from services import crypto_service` resolve. Top-of-file `sys.path.insert` (as in `test_folders_api.py` lines 11-13) is optional but matches the convention in DB-touching test files.

---

### `backend/tests/test_config.py` (test, unit) — MODIFY

**Analog:** the file itself — add a pair mirroring `test_chat_max_iterations_default` / `test_chat_max_iterations_env_override` (lines 5-17). Note this file uses `Settings()` DIRECTLY (not `get_settings()`), so it does NOT need `cache_clear`:
```python
def test_key_encryption_secret_default():
    from config import Settings
    assert Settings().key_encryption_secret == ""

def test_key_encryption_secret_env_override(monkeypatch):
    monkeypatch.setenv("KEY_ENCRYPTION_SECRET", "abc")
    from config import Settings
    assert Settings().key_encryption_secret == "abc"
```
> Follow the existing one-line-docstring style (lines 6, 13) and the `monkeypatch.setenv` → `Settings()` → `assert` shape exactly.

---

### `backend/tests/test_sql_keys_lockdown.py` (test, unit SEC-02 probe) — NEW

**Analog:** `backend/tests/test_folders_api.py` — the canonical `patch("<module>.get_supabase", return_value=mock_db)` + MagicMock builder-chain pattern. For `sql_service`, the patch target is `services.sql_service.get_supabase` (confirmed: `sql_service.py` line 3 imports `get_supabase` into its own namespace; mirror the `test_folders_api.py` line-151 pattern but with the `services.sql_service` module path).

**Mock-Supabase chain + `_result` helper** (`test_folders_api.py` lines 43-61) — for an RPC the chain is `db.rpc(...).execute()`:
```python
# test_folders_api.py shape to adapt:
def _result(data):
    r = MagicMock()
    r.data = data
    return r

# RPC-style adaptation for execute_sql -> db.rpc("execute_readonly_query", {...}).execute():
mock_db = MagicMock()
mock_db.rpc.return_value.execute.return_value = _result([])   # empty == blocked
with patch("services.sql_service.get_supabase", return_value=mock_db):
    result = execute_sql(user_id=TEST_USER_ID, sql="select * from user_api_keys")
    assert result["success"] is False or result["rows"] == []
```
> **Probe-layer decision (RESEARCH Open Question 2, MEDIUM):** the planner must choose where the allowlist is asserted. Two valid seams: (a) UNIT — assert `execute_sql` / a pure-Python allowlist helper rejects `select * from user_api_keys` (deterministic, mockable, the durable CI gate); (b) INTEGRATION (optional, marker-gated) — hit the live dev DB to prove the real REVOKE denies the query. RESEARCH Pitfall 5 warns: a purely-mocked probe that never asserts the SQL was rejected is a false PASS. Prefer (a) for CI + a clearly-marked optional (b); the live REVOKE is also verified manually at the dev/prod apply step (D-05).
> Note `execute_sql`'s real signature is `execute_sql(user_id: str, query: str)` (`sql_service.py` line 48) — the RESEARCH example uses `sql=` as a kwarg name; use the real param name `query=` or positional.

---

## Shared Patterns

### Service-role DB access (RLS bypass) — backend read/write of `user_api_keys`
**Source:** `backend/database.py` lines 5-7
**Apply to:** any Phase 9 code that touches `user_api_keys` (none writes it this phase, but Phase 10/11 will). The backend uses the service-role client which bypasses BOTH RLS and the REVOKE — that is by design; the RLS policies + REVOKE are defense-in-depth against the `authenticated` (SQL-tool / future anon-client) path only.
```python
def get_supabase() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url_resolved, settings.supabase_service_role_key)
```

### Settings access deferred to call-time (so tests can `cache_clear`)
**Source:** `backend/services/web_search_service.py` line 10, `backend/config.py` lines 143-145
**Apply to:** `crypto_service.py` — call `get_settings()` INSIDE `_multifernet()`, never read the secret at import time. This is what lets `test_crypto_service.py` swap keys via `monkeypatch.setenv` + `get_settings.cache_clear()`.

### Own-row RLS policy wording
**Source:** `supabase/migrations/20240301000020_update_rls_policies.sql` lines 19-36 (take the `auth.uid() = user_id` form; drop the `OR visibility = 'public'` clause for the keys table)
**Apply to:** all four policies on `user_api_keys` in migration 025.

### Migration header-comment + transaction-per-file convention
**Source:** `supabase/migrations/20240301000018_create_folders_table.sql` lines 1-4 (purpose + RLS intent + Depends-on header)
**Apply to:** both new migrations (025, 026). Sequential numbering `20240301000NNN_*.sql`; each file = one transaction.

### Config-test shape (default + env-override pair)
**Source:** `backend/tests/test_config.py` lines 5-17
**Apply to:** the two new tests added to `test_config.py`.

### `@lru_cache` cache_clear discipline
**Source:** `backend/config.py` line 143 (`@lru_cache`); RESEARCH note line 349
**Apply to:** `test_crypto_service.py` and any future test that mutates `KEY_ENCRYPTION_SECRET` via `monkeypatch.setenv` then exercises code reading `get_settings()`. (`test_config.py` is exempt — it constructs `Settings()` directly.)

## No Analog Found

No file in this phase lacks an analog. Two sub-patterns are genuinely net-new (but extend/sit-beside existing code), called out so the planner does not search for a non-existent precedent:

| Net-new element | Where it lives | Note |
|------|------|------|
| `revoke select ... from authenticated` | migration 025 | No prior REVOKE in the repo's migrations; it is a standard Postgres DDL statement (RESEARCH §Pattern 2, verified privilege-before-RLS semantics). |
| FROM-table allowlist regex loop in the RPC | migration 026 | The only genuinely new algorithmic logic this phase; extends the already-tested `execute_readonly_query` (migration 015). Exact regex is executor's discretion. |

## Metadata

**Analog search scope:** `backend/services/`, `backend/` (config, auth, database), `supabase/migrations/`, `backend/tests/`
**Files scanned (read):** `config.py`, `auth.py`, `database.py`, `services/sql_service.py`, `services/web_search_service.py`, `migrations/{015,018,020}`, `tests/{config, conftest, folders_api}`, plus a migrations-dir listing and a `get_supabase`/`rpc` usage grep across `backend/tests/`.
**Key reconciliation applied:** SQL allowlist = `{threads, messages, documents, document_chunks}` per CONTEXT D-01 (reconciled), SUPERSEDING the RESEARCH-era `{documents, document_chunks, folders}`. RESEARCH Open Question 1 resolved.
**Pattern extraction date:** 2026-06-18
