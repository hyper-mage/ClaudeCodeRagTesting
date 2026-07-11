# Phase 9: Crypto + Encrypted Key Storage Foundation - Research

**Researched:** 2026-06-18
**Domain:** App-layer symmetric encryption (Fernet/MultiFernet) + Supabase RLS migration + Postgres privilege/RLS interaction + pytest verification
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**SQL-tool lockdown (SEC-02)**
- **D-01:** Defense-in-depth — BOTH `REVOKE SELECT ON user_api_keys FROM authenticated` AND add an explicit FROM-table allowlist to `execute_readonly_query` so the Text-to-SQL tool can only query `documents`, `document_chunks`, `folders`. The keys table (and the future `user_preferences` table) are excluded by default, not by enumeration.
  - Rationale: `execute_readonly_query` does `SET LOCAL role = 'authenticated'` (verified in `supabase/migrations/20240301000015_execute_readonly_query.sql`), so RLS is active during execution — but a user's OWN-row ciphertext would still be returnable to the model under their JWT. REVOKE removes that path; the allowlist is a second independent gate.

**Key rotation (KEY-02)**
- **D-02:** Full rotation path this phase via Fernet `MultiFernet` — `key_version` column on `user_api_keys`; decrypt accepts current + previous key; lazy re-encrypt on read when a row is on an older key; rotation runbook documented. Satisfies ROADMAP success criterion #4. Cheap because MultiFernet handles multi-key decrypt natively.

**Migration rollout & secret management (KEY-02)**
- **D-03:** Apply the `user_api_keys` migration to the **dev** Supabase project (`.env`) during this phase; **prod** (`.env.prod`) is applied at the phase's deploy step, not now — keeps prod data/keys isolated per the dual-env discipline. See [[project_dual_supabase_envs]].
- **D-04:** `KEY_ENCRYPTION_SECRET` is a **distinct 32-byte key per environment** — dev value in `.env`, a SEPARATE prod value in `.env.prod` and the Fly secret store. Never share the dev key with prod. Add to `Settings` in `backend/config.py` (empty default, like other secrets). Decrypt happens only in-backend per request; the secret is never logged, traced, or returned.

**Verification (SEC-02 acceptance gate)**
- **D-05:** Automated `pytest` in `backend/tests/`: (a) a probe that drives the SQL tool / `execute_readonly_query` with `select * from user_api_keys` and asserts empty result or error; (b) an encrypt → decrypt round-trip test (incl. a MultiFernet rotation round-trip). This is the durable regression gate; manual prod check happens at the deploy step.

**Carried forward (locked by research — do not re-litigate)**
- Fernet via the already-pinned `cryptography 46.0.5` — **no new dependency** (same lib used for ES256 JWT in `backend/auth.py`).
- One OpenRouter key per user → `user_api_keys` PK = `user_id` (FK to auth.users). Multi-provider / multiple keys are out of scope (anti-feature).
- Table stores ciphertext only + `key_version` + created/updated timestamps; per-user RLS mirrors the existing mixed-visibility policy pattern.

### Claude's Discretion
- Exact column names/types, migration filename (next is `20240301000025_*`), `crypto_service` function signatures, and pytest fixture wiring — planner/executor decide, following existing conventions.

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope.
- Observability `sk-or-` scrub belongs to Phase 11 (backend) / Phase 10 (frontend Sentry) per research, NOT Phase 9. OAuth/connect to Phase 10. Per-request key+model resolution to Phase 11.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| KEY-02 | User's OpenRouter key is stored encrypted at rest, RLS-scoped to the user, and never returned to the frontend | Fernet/MultiFernet encrypt-at-rest (verified §Standard Stack); `user_api_keys` table with per-user RLS + `key_version` (§Architecture Patterns); rotation via `MultiFernet.rotate()` (verified empirically); backend-only decrypt via service-role client (§Architecture). NOTE: "never returned to the frontend" is partly enforced in Phase 9 (no endpoint exposes the key) but the connect/status endpoints land in Phase 10 — Phase 9 only builds the storage + crypto layer. |
| SEC-02 | The Text-to-SQL tool cannot read the user-keys table (secret column REVOKE'd from the `authenticated` role + RPC table allowlist) | `REVOKE SELECT ON user_api_keys FROM authenticated` (privilege-before-RLS semantics verified, §Common Pitfalls #1); FROM-table allowlist added to `execute_readonly_query` (§Architecture Pattern 3); pytest exfiltration probe via `execute_sql` (§Validation Architecture). |
</phase_requirements>

## Summary

This phase is a backend-and-database foundation with **zero frontend and zero new dependencies**. Everything needed is already installed: `cryptography 46.0.5` provides `Fernet`/`MultiFernet` (verified empirically below), `supabase-py` provides the service-role client that reads/writes the keys table bypassing RLS, and `pytest 8.4.2` + the existing `backend/tests/` harness host the regression gate. The work is four tightly-scoped deliverables: (1) a `crypto_service` wrapping MultiFernet; (2) a `KEY_ENCRYPTION_SECRET` setting in `config.py`; (3) the `user_api_keys` migration (`...025`) with per-user RLS + `key_version`; (4) hardening `execute_readonly_query` with a FROM-table allowlist + `REVOKE SELECT ... FROM authenticated`.

The single highest-value research finding is the **Postgres privilege-vs-RLS precedence rule** (verified against postgresql.org): table-level privileges are evaluated **before** row-level security. This means `REVOKE SELECT ON user_api_keys FROM authenticated` completely denies the SQL tool's read path even though the table will also have an own-row RLS SELECT policy — REVOKE wins, and no policy can override it. The backend's service-role client is unaffected (it bypasses both). This makes success criterion #3 satisfiable by REVOKE alone, with the FROM-table allowlist as the independent second gate D-01 requires.

I verified the MultiFernet API directly against the installed library: `Fernet.generate_key()` yields a 44-char url-safe base64 string (32 raw bytes); `MultiFernet([f_new, f_old])` encrypts with the **first** key and decrypts with **any** key in the list; `.rotate(token)` re-encrypts an existing token under the primary key — this is exactly the lazy-re-encrypt + dual-key-decrypt rotation path D-02 requires, available with no extra code beyond key ordering.

**Primary recommendation:** Build `crypto_service` on `MultiFernet` from day one (parse `KEY_ENCRYPTION_SECRET` as a comma-separated key list, new-key-first); use `MultiFernet.rotate()` for the lazy re-encrypt; store the encrypted blob + an integer `key_version` column; harden the RPC with a FROM-table allowlist of exactly `{documents, document_chunks, folders}` PLUS `REVOKE SELECT ON user_api_keys FROM authenticated`; and prove all four success criteria with pytest (mock-DB unit tests for crypto + config; an `execute_sql`-driven probe for the SEC-02 gate).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Encrypt/decrypt user key | API / Backend (`crypto_service.py`) | — | Plaintext must exist only in backend memory; master key is a backend-only secret. Never the browser, never the DB. |
| Master secret custody | Config / Secrets (`config.py` + Fly/.env) | — | `KEY_ENCRYPTION_SECRET` lives in env/Fly secrets, loaded via pydantic-settings. Decryption-key separation from the ciphertext store is the whole point. |
| Persist ciphertext + key_version | Database / Storage (`user_api_keys`) | — | Postgres `text` column holds Fernet token; `key_version int` enables rotation tracking. Ciphertext only — never plaintext. |
| Own-row access control | Database / Storage (RLS on `user_api_keys`) | — | Per-user `auth.uid() = user_id` policies — defense-in-depth against any future anon-client path. Backend uses service-role (bypasses RLS). |
| SQL-tool table gating | Database / Storage (`execute_readonly_query` RPC + REVOKE) | API (`sql_service.execute_sql`) | The lockdown is two DB-layer gates (REVOKE privilege + FROM-table allowlist inside the SECURITY DEFINER RPC). The API layer (`execute_sql`) just forwards the model's SQL string. |
| Rotation orchestration | API / Backend (`crypto_service` + runbook) | Database (lazy re-encrypt UPDATE) | MultiFernet decrypt-with-fallback + `.rotate()` is backend logic; the re-encrypted row + bumped `key_version` is written back to the DB. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `cryptography` (`Fernet`/`MultiFernet`) | **46.0.5** (installed; latest 49.0.0) `[VERIFIED: pip index + import]` | Authenticated symmetric encryption (AES-128-CBC + HMAC-SHA256) of the user key at rest; multi-key rotation | Already pinned and imported (ES256 JWT path in `auth.py`). Zero new deps. Fernet API is stable across all listed versions. `[VERIFIED: backend/requirements.txt line cryptography==46.0.5]` |
| `supabase` (service-role client) | **2.13.0** `[CITED: CLAUDE.md tech stack]` | Backend read/write of `user_api_keys`, bypassing RLS | Established `get_supabase()` pattern in `database.py` uses the service-role key. `[VERIFIED: backend/database.py]` |
| `pydantic-settings` | **2.9.1** `[CITED: CLAUDE.md]` | Load `KEY_ENCRYPTION_SECRET` from env (`.env` / `.env.prod` via `ENV_FILE`) | The `Settings` + `@lru_cache get_settings()` pattern is the project's only config path. `[VERIFIED: backend/config.py]` |
| `pytest` (+ `pytest-asyncio`) | **8.4.2** / **0.23.8** `[VERIFIED: backend/requirements.txt]` | The D-05 regression gate (crypto round-trip, rotation, SEC-02 probe) | `backend/tests/` already uses this harness with `TestClient` + mock Supabase. `[VERIFIED: backend/tests/conftest.py, test_folders_api.py]` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python stdlib `secrets` / `base64` | stdlib | (Optional) generate a `KEY_ENCRYPTION_SECRET` value | Prefer `Fernet.generate_key()` — produces the exact url-safe base64 32-byte format Fernet requires. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Fernet (app-layer) | Supabase Vault / pgsodium / pgcrypto | REJECTED in milestone STACK.md — key lives near data in the DB cluster, worse isolation than an env-held master key decrypted only in the backend. Adds migration + operational surface for no security gain here. `[CITED: .planning/research/STACK.md §1]` |
| `MultiFernet` rotation | Single `Fernet` + no `key_version` | REJECTED by D-02 and Pitfall 4 — a painful all-rows migration at first rotation. MultiFernet gives dual-key decrypt + `.rotate()` for free. |

**Installation:**
```bash
# NO new packages. cryptography==46.0.5 is already in backend/requirements.txt.

# Generate a per-environment master key (run once per env, store the OUTPUT, never commit):
cd backend && venv/Scripts/python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# -> set KEY_ENCRYPTION_SECRET=<value> in .env (dev) and a SEPARATE value in .env.prod + Fly secrets (prod, at deploy step per D-03)
```

**Version verification:**
- `cryptography`: installed `46.0.5`, latest on PyPI `49.0.0` (checked 2026-06-18). No upgrade needed — Fernet/MultiFernet API identical. `[VERIFIED: pip index versions cryptography → INSTALLED: 46.0.5]`
- `pytest`: `8.4.2`, `pytest-asyncio`: `0.23.8`. `[VERIFIED: backend/requirements.txt]`

## Architecture Patterns

### System Architecture Diagram

```
                         WRITE PATH (future Phase 10 caller; built here)
  plaintext key  ──►  crypto_service.encrypt_key()  ──►  MultiFernet(primary).encrypt()
                                                              │
                                                              ▼
                                            service-role Supabase client
                                                              │  (bypasses RLS)
                                                              ▼
                                   user_api_keys: { user_id PK, encrypted_key, key_version, ... }
                                                  (ciphertext only — plaintext never stored)

                         READ / DECRYPT PATH (future Phase 11 caller; built here)
  user_id  ──►  service-role select encrypted_key, key_version
                          │
                          ▼
          crypto_service.decrypt_key(ciphertext)  ──►  MultiFernet([new, old]).decrypt()
                          │                                    │ (tries each key)
                          │                                    ▼
                          │                          if decrypted under an OLD key:
                          │                                MultiFernet.rotate() → re-encrypt
                          │                                UPDATE row set encrypted_key, key_version
                          ▼
                  plaintext (in-memory, this request only — never logged/returned)

                         SQL-TOOL EXFILTRATION GATE (the SEC-02 lockdown — D-01)
  model-authored SQL  ──►  chat.py query_database tool  ──►  sql_service.execute_sql(user_id, sql)
                                                                   │  service-role rpc()
                                                                   ▼
                              execute_readonly_query (SECURITY DEFINER)
                                  ├─ keyword allowlist (existing: SELECT/WITH only, no DDL)
                                  ├─ [NEW] FROM-table allowlist: {documents, document_chunks, folders}
                                  ├─ SET LOCAL role = 'authenticated'   ← REVOKE applies here
                                  └─ EXECUTE 'SELECT * FROM (<sql>) sub LIMIT n'
                                           │
                                           ▼
                              user_api_keys: SELECT DENIED for role 'authenticated'
                              (privilege check precedes RLS → returns error / nothing)
```

### Recommended File Structure
```
backend/
├── services/
│   └── crypto_service.py            # NEW — encrypt_key / decrypt_key / (rotation helper) on MultiFernet
├── config.py                        # MODIFIED — add key_encryption_secret: str = ""
└── tests/
    ├── test_crypto_service.py       # NEW — round-trip + rotation (D-05b)
    ├── test_config.py               # MODIFIED or NEW test — KEY_ENCRYPTION_SECRET default + env override
    └── test_sql_keys_lockdown.py    # NEW — SEC-02 exfiltration probe (D-05a)

supabase/migrations/
├── 20240301000025_create_user_api_keys.sql       # NEW — table + RLS + key_version + REVOKE
└── 20240301000026_harden_sql_tool_allowlist.sql  # NEW (or fold into 025) — FROM-table allowlist in execute_readonly_query
```
> Migration split (025 storage, 026 RPC hardening) vs. single file is Claude's discretion. Note: 025 is the next free number `[VERIFIED: ls migrations → last is ...024]`. If split, 026 follows.

### Pattern 1: crypto_service on MultiFernet (rotation-ready from day one)
**What:** A minimal service wrapping `MultiFernet`. Parse `KEY_ENCRYPTION_SECRET` as a comma-separated key list (new key first). Encrypt with the primary; decrypt tries all keys; rotation re-encrypts under the primary.
**When to use:** Always — D-02 mandates the rotation path this phase, and MultiFernet costs nothing extra over plain Fernet.
**Example (VERIFIED against installed `cryptography 46.0.5`):**
```python
# backend/services/crypto_service.py
from cryptography.fernet import Fernet, MultiFernet
from config import get_settings

def _multifernet() -> MultiFernet:
    # KEY_ENCRYPTION_SECRET = comma-separated url-safe base64 32-byte keys, NEW KEY FIRST.
    # Single-key (no rotation in progress) is just one entry.
    keys = [k.strip() for k in get_settings().key_encryption_secret.split(",") if k.strip()]
    return MultiFernet([Fernet(k.encode()) for k in keys])

def encrypt_key(plaintext: str) -> str:
    return _multifernet().encrypt(plaintext.encode()).decode()   # encrypts under the FIRST key

def decrypt_key(ciphertext: str) -> str:
    return _multifernet().decrypt(ciphertext.encode()).decode()  # tries EACH key in order

def rotate_token(ciphertext: str) -> str:
    # Re-encrypt an existing token under the current PRIMARY key (lazy rotation).
    return _multifernet().rotate(ciphertext.encode()).decode()
```
> **Empirically verified behavior** (`venv/Scripts/python.exe`, cryptography 46.0.5):
> - `Fernet.generate_key()` → 44-char url-safe base64 string (32 raw bytes). `[VERIFIED: key_len 44]`
> - `MultiFernet([Fernet(k1), Fernet(k2)]).encrypt(...)` then `.decrypt(...)` round-trips. `[VERIFIED]`
> - Encrypting with `[k1, k2]` ordering, then decrypting with a MultiFernet that only has `k2`, FAILS — confirming encrypt uses the first key only. `[VERIFIED]`
> - `MultiFernet([k_new, k_old]).rotate(old_token)` produces a token decryptable by `MultiFernet([k_new])` alone — proving rotation success criterion #4. `[VERIFIED: rotate_ok]`

### Pattern 2: `user_api_keys` table (mirrors mixed-visibility RLS precedent + adds REVOKE)
**What:** PK = `user_id` (one key per user), ciphertext-only column, `key_version int`, per-user RLS policies, AND a `REVOKE SELECT ... FROM authenticated`.
**When to use:** The storage migration (D-03, dev only this phase).
**Example (synthesized from ARCHITECTURE.md schema + the verified 020 RLS pattern + D-02 key_version + D-01 REVOKE):**
```sql
-- 20240301000025_create_user_api_keys.sql
create table user_api_keys (
  user_id        uuid primary key references auth.users(id) on delete cascade,
  provider       text not null default 'openrouter',
  encrypted_key  text not null,                 -- Fernet ciphertext (base64) — never plaintext
  key_version    integer not null default 1,    -- D-02: which master key encrypted this row
  key_label      text,                          -- OpenRouter-assigned display label (set in Phase 10)
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

alter table user_api_keys enable row level security;

-- Per-user own-row policies (mirror migration 020 pattern: auth.uid() = user_id).
-- Defense-in-depth ONLY — backend uses the service-role client (bypasses RLS).
create policy "Users can view own key row"   on user_api_keys for select using (auth.uid() = user_id);
create policy "Users can insert own key row" on user_api_keys for insert with check (auth.uid() = user_id);
create policy "Users can update own key row" on user_api_keys for update using (auth.uid() = user_id);
create policy "Users can delete own key row" on user_api_keys for delete using (auth.uid() = user_id);

-- SEC-02 GATE 1 (D-01): revoke the SQL-tool role's table access entirely.
-- Privilege is checked BEFORE RLS, so this denies the own-row read path too. [VERIFIED: postgresql.org]
-- The service-role backend is UNAFFECTED (it does not run as 'authenticated').
revoke select on user_api_keys from authenticated;
```
> **Critical:** `execute_readonly_query` blocks the literal keywords `grant|revoke` in user-submitted SQL (line 26 of migration 015), so the REVOKE statement must live in the migration file, never be issued through the RPC.

### Pattern 3: FROM-table allowlist inside `execute_readonly_query` (SEC-02 GATE 2)
**What:** Add a positive allowlist check so the RPC only executes queries whose FROM/JOIN targets are in `{documents, document_chunks, folders}`. Default-deny — new tables (keys, preferences) are excluded unless explicitly added.
**When to use:** The RPC-hardening migration (D-01, second independent gate).
**Design constraints (from reading migration 015):**
- The RPC wraps the user SQL as `EXECUTE format('SELECT ... FROM (<sql>) sub ...')`. The allowlist must inspect the **inner** `<sql>` (`sanitized`), not the wrapper.
- Existing gates remain: SELECT/WITH-only (line 21), keyword block incl. `grant|revoke|drop|...` (line 26), `SET LOCAL role = 'authenticated'` (line 32), row limit (line 36).
- **Recommended approach:** regex-extract every identifier following `from` / `join` in `sanitized` (case-insensitive), then assert each is in the allowlist; `RAISE EXCEPTION` otherwise. A deny-list of forbidden table names is the wrong shape (D-01 mandates default-deny via allowlist).
**Example (illustrative — exact regex is executor's discretion):**
```sql
-- inside execute_readonly_query, after the keyword block, before SET LOCAL role:
-- Extract FROM/JOIN targets and require each in the allowlist.
DECLARE
  tbl TEXT;
BEGIN
  FOR tbl IN
    SELECT lower((regexp_matches(sanitized, '(?:from|join)\s+["]?([a-z_][a-z0-9_]*)', 'gi'))[1])
  LOOP
    IF tbl NOT IN ('documents', 'document_chunks', 'folders') THEN
      RAISE EXCEPTION 'Query references a non-allowlisted table: %', tbl;
    END IF;
  END LOOP;
END;
```
> See **Open Question 1** — the allowlist `{documents, document_chunks, folders}` (D-01) CONFLICTS with the current `QUERYABLE_SCHEMA` advertised to the model, which lists `threads, messages, documents, document_chunks` (NOT `folders`). The planner MUST reconcile this before implementation.

### Anti-Patterns to Avoid
- **Reusing `supabase_jwt_secret` (or any existing secret) as the encryption key:** co-located blast radius; D-04 + Pitfall 4 mandate a dedicated, independently-generated 32-byte key per env. `[CITED: PITFALLS.md Pitfall 4]`
- **Single `Fernet` + no `key_version`:** forces a painful all-rows migration at first rotation. Use MultiFernet + `key_version` from day one. `[CITED: PITFALLS.md tech-debt table]`
- **Deny-list of table names in the RPC:** D-01 requires a positive allowlist (default-deny) so future tables (keys, preferences) are excluded automatically.
- **Returning the ciphertext (or plaintext) to any client path:** even the encrypted blob is needless exposure. No Phase 9 endpoint should select the key column into a response (status/connect endpoints land in Phase 10 and return booleans/labels only). `[CITED: ARCHITECTURE.md Anti-Pattern 1]`
- **Issuing REVOKE/GRANT through the RPC:** blocked by the keyword filter — put it in the migration file.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Symmetric encryption of the key | Custom AES + HMAC wrapper | `cryptography.fernet.Fernet` | Fernet bundles AES-128-CBC + HMAC-SHA256 + timestamp + url-safe base64 framing; rolling your own invites IV reuse / padding-oracle / MAC mistakes. |
| Multi-key decrypt + rotation | Manual "try key A, except, try key B" loops + bespoke re-encrypt | `cryptography.fernet.MultiFernet` + `.rotate()` | Native decrypt-with-fallback and atomic re-encrypt; verified working in 46.0.5. |
| Master-key generation | `os.urandom(32)` + manual base64 | `Fernet.generate_key()` | Produces the exact url-safe base64 32-byte format `Fernet(key)` expects; mismatched encoding is the #1 Fernet setup error. |
| SQL safety for the tool | New parser/validator from scratch | Extend the existing `execute_readonly_query` gates | The RPC already does SELECT-only + keyword block + RLS context + row limit; only the FROM-table allowlist is new. |
| Backend RLS bypass for key I/O | Re-implement service-role auth | Existing `get_supabase()` (service-role client) | Established pattern in `database.py`; bypasses RLS server-side as designed. |

**Key insight:** This phase has essentially no novel algorithmic work — it is composition of already-installed, audited primitives. The only genuinely new logic is the FROM-table allowlist regex inside the RPC, and even that extends an existing, tested function.

## Runtime State Inventory

> This is NOT a rename/refactor phase — it is greenfield additive (new table, new service, new column, RPC extension). The five categories are answered to confirm no hidden runtime state is disturbed.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — `user_api_keys` is a NEW table; no existing rows reference it. The migration adds an empty table. | None |
| Live service config | `execute_readonly_query` RPC exists in BOTH the dev and prod Supabase projects. This phase modifies it in **dev only** (D-03); prod RPC change ships at the deploy step. The RPC is not exported to git beyond the migration file — verify the dev project's live RPC matches migration 015 before patching. | Re-apply hardened RPC migration to dev; prod deferred to deploy step |
| OS-registered state | None — no Task Scheduler / pm2 / systemd entries touch crypto or the keys table. | None |
| Secrets/env vars | NEW env var `KEY_ENCRYPTION_SECRET` — distinct value per env (D-04). Lives in `.env` (dev, this phase), `.env.prod` + Fly secrets (prod, deploy step). Not in git. No EXISTING secret is renamed or reused. | Generate + set dev value; add to `Settings`; prod value at deploy |
| Build artifacts / installed packages | None — no new pip package, no egg-info regeneration. `cryptography 46.0.5` already installed in `backend/venv/`. | None |

**Canonical question — after every repo file is updated, what runtime state still has stale config?** The **prod Supabase project's `execute_readonly_query` RPC** remains un-hardened until the deploy step (intentional, per D-03). Until then, the prod SQL tool has no `user_api_keys` table to leak (prod migration not applied), so there is no exposure window — but the planner must ensure the prod RPC hardening and the prod table migration ship **together** at deploy, never the table without the REVOKE.

## Common Pitfalls

### Pitfall 1: Assuming RLS protects the keys table from the SQL tool (it does not, by itself)
**What goes wrong:** Relying on the per-user RLS SELECT policy to keep the Text-to-SQL tool away from `user_api_keys`. Under the user's JWT (`SET LOCAL role = 'authenticated'` + `request.jwt.claim.sub`), RLS would still return the user's OWN ciphertext row to the model — a needless secret exposure, and a mass-exfiltration vector if the policy is ever misconfigured.
**Why it happens:** The RPC's only table-scoping mechanism today is RLS; devs assume "RLS on = safe."
**How to avoid:** `REVOKE SELECT ON user_api_keys FROM authenticated`. **Postgres checks table privileges BEFORE applying RLS** `[VERIFIED: postgresql.org/docs/current/ddl-rowsecurity.html — "all normal access ... must be allowed by a row security policy" but table-level privilege is the prerequisite gate]`. With SELECT revoked from `authenticated`, the query is rejected outright; no RLS policy can re-grant it. The service-role backend is unaffected (does not run as `authenticated`). Add the FROM-table allowlist as the independent second gate (D-01).
**Warning signs:** A `query_database` call whose SQL references `user_api_keys`, `key`, `secret`, or `auth`; the assistant surfacing base64 blobs.

### Pitfall 2: Fernet key encoding mismatch
**What goes wrong:** `KEY_ENCRYPTION_SECRET` stored as a raw 32-byte string or hex instead of url-safe base64 → `Fernet(key)` raises `ValueError: Fernet key must be 32 url-safe base64-encoded bytes`.
**Why it happens:** Generating the key with `os.urandom(32)` or a password instead of `Fernet.generate_key()`.
**How to avoid:** Always generate with `Fernet.generate_key().decode()` (produces the 44-char base64 form). The `crypto_service` calls `.encode()` on the stored string before passing to `Fernet`. `[VERIFIED: key_len 44 empirically]`
**Warning signs:** `ValueError` at first encrypt; a stored secret that is not 44 chars / lacks the base64 alphabet.

### Pitfall 3: Master key in dev `.env` accidentally shared with prod
**What goes wrong:** Copying the dev `KEY_ENCRYPTION_SECRET` into `.env.prod` / Fly — a single leak then compromises both environments; rotation in one breaks the other.
**Why it happens:** Convenience copy-paste; the dual-env discipline isn't enforced by tooling.
**How to avoid:** Generate a **separate** `Fernet.generate_key()` per env (D-04). Dev value never leaves `.env`. Prod value generated and set at the deploy step only.
**Warning signs:** Identical secret in `.env` and `.env.prod`; a single key documented as "the encryption key."

### Pitfall 4: RPC allowlist regex breaks legitimate queries or misses CTEs/aliases
**What goes wrong:** A FROM-table allowlist regex that's too strict rejects valid queries (e.g., subqueries, CTE names, table aliases), or too loose (matches a column named `from_date`, or misses `JOIN`).
**Why it happens:** SQL identifier extraction via regex is inherently approximate; the RPC wraps the query in a subquery, complicating naive parsing.
**How to avoid:** Match identifiers after `from`/`join` keywords (word-boundary, case-insensitive, optional quoting); test against the actual legitimate queries the model emits. CTE names (`WITH x AS ...`) will appear as FROM targets — decide whether to allow CTE self-references (likely yes). Keep a focused regression test of real `documents`/`document_chunks`/`folders` queries that MUST still pass.
**Warning signs:** A previously-working metadata/stats query now errors; the allowlist rejects a CTE alias.

### Pitfall 5: The SEC-02 probe gives a false PASS against a mock
**What goes wrong:** A pytest that mocks the Supabase RPC will "pass" regardless of whether the real REVOKE/allowlist exists — testing the mock, not the protection.
**Why it happens:** `backend/tests/` predominantly mocks the DB (see `test_folders_api.py` MockSupabase pattern); a mocked `execute_sql` can't exercise real Postgres privilege checks.
**How to avoid:** Decide the probe's layer explicitly (see Validation Architecture). Two valid strategies: (a) a UNIT test asserting `execute_sql`/the RPC's allowlist logic rejects `select * from user_api_keys` (tests the allowlist gate, mockable); (b) an INTEGRATION test against the live dev Supabase project that proves the REVOKE actually denies the query (tests the real privilege gate, needs DB creds). For a durable CI gate, prefer (a) for the allowlist + a clearly-marked optional integration test for the REVOKE; the REVOKE itself is also verified manually at the dev/prod deploy steps per D-05.
**Warning signs:** A "SEC-02 passing" test that never touches real Postgres and never asserts the SQL string was rejected.

## Code Examples

### Encrypt → decrypt round-trip + rotation (D-05b regression test)
```python
# backend/tests/test_crypto_service.py
# Source: verified MultiFernet behavior, cryptography 46.0.5
from cryptography.fernet import Fernet

def test_encrypt_decrypt_roundtrip(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("KEY_ENCRYPTION_SECRET", key)
    from config import get_settings; get_settings.cache_clear()  # @lru_cache — clear between tests
    from services import crypto_service
    ct = crypto_service.encrypt_key("sk-or-v1-example")
    assert ct != "sk-or-v1-example"                 # ciphertext, not plaintext
    assert crypto_service.decrypt_key(ct) == "sk-or-v1-example"

def test_rotation_decrypts_old_and_reencrypts(monkeypatch):
    old = Fernet.generate_key().decode()
    new = Fernet.generate_key().decode()
    monkeypatch.setenv("KEY_ENCRYPTION_SECRET", old)
    from config import get_settings; get_settings.cache_clear()
    from services import crypto_service
    token_old = crypto_service.encrypt_key("sk-or-v1-example")
    # rotate: new key first, old key still present for decrypt
    monkeypatch.setenv("KEY_ENCRYPTION_SECRET", f"{new},{old}")
    get_settings.cache_clear()
    rotated = crypto_service.rotate_token(token_old)
    # rotated token now decryptable with the NEW key alone
    monkeypatch.setenv("KEY_ENCRYPTION_SECRET", new)
    get_settings.cache_clear()
    assert crypto_service.decrypt_key(rotated) == "sk-or-v1-example"
```
> NOTE: `get_settings` is `@lru_cache`d (`config.py` line 143). Tests that change `KEY_ENCRYPTION_SECRET` via `monkeypatch.setenv` MUST call `get_settings.cache_clear()` (or instantiate `Settings()` directly, as `test_config.py` does). `[VERIFIED: backend/config.py, backend/tests/test_config.py]`

### Config wiring test (mirrors existing test_config.py pattern)
```python
# Source: backend/tests/test_config.py existing pattern
def test_key_encryption_secret_default():
    from config import Settings
    assert Settings().key_encryption_secret == ""        # empty default like other secrets

def test_key_encryption_secret_env_override(monkeypatch):
    monkeypatch.setenv("KEY_ENCRYPTION_SECRET", "abc")
    from config import Settings
    assert Settings().key_encryption_secret == "abc"
```

### SEC-02 exfiltration probe (D-05a — allowlist-layer unit test)
```python
# backend/tests/test_sql_keys_lockdown.py
# Drives the SQL tool path; asserts a keys-table query is rejected (not executed).
from unittest.mock import patch, MagicMock
from services.sql_service import execute_sql

def test_keys_table_query_blocked():
    # If the allowlist logic lives in execute_readonly_query (Postgres), this needs the
    # live dev DB. If a pre-flight allowlist guard is added in execute_sql, assert here.
    # Strategy decision lives in Validation Architecture / Open Question 1.
    result = execute_sql(user_id="11111111-1111-1111-1111-111111111111",
                         sql="select * from user_api_keys")  # via the model's tool
    assert result["success"] is False or result["rows"] == []
```
> The exact probe layer depends on where the allowlist is enforced (DB-only vs. a backend pre-flight guard). See Validation Architecture below — the planner should choose and the Wave 0 test file reflects it.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| DB-side column encryption (pgcrypto/pgsodium) | App-layer Fernet, key in env, decrypt only in backend | Project decision (STACK.md) | Key never lives in the DB cluster; a DB dump alone leaks nothing. |
| Single-key encryption, rotate-by-migration | MultiFernet decrypt-with-fallback + lazy `.rotate()` | This phase (D-02) | Zero-downtime rotation; no big-bang re-encrypt migration. |
| RLS-only table scoping for the SQL tool | Table-privilege REVOKE (precedes RLS) + positive FROM allowlist | This phase (D-01) | Prompt-injection cannot reach the keys table even under the user's own JWT. |

**Deprecated/outdated:** None relevant. `cryptography` Fernet/MultiFernet API is stable from v35 through the latest 49.0.0.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The legitimate Text-to-SQL surface that must keep working is captured by the allowlist `{documents, document_chunks, folders}` (per D-01) — but the live `QUERYABLE_SCHEMA` advertises `threads, messages, documents, document_chunks`. | Architecture Pattern 3 / Open Questions | If `threads`/`messages` queries are legitimately used, the allowlist breaks them; if `folders` is never queried by the model, allowing it is harmless but unused. **Planner must reconcile — this is a locked-decision-vs-code conflict.** |
| A2 | `KEY_ENCRYPTION_SECRET` is best modeled as a comma-separated key list so MultiFernet rotation needs no schema/config reshape later. | Pattern 1 | If the planner prefers two distinct settings (`KEY_ENCRYPTION_SECRET` + `KEY_ENCRYPTION_SECRET_PREVIOUS`), the parsing differs — both satisfy D-02/D-04. Low risk; cosmetic. |
| A3 | The dev Supabase project's live `execute_readonly_query` matches migration 015 verbatim (no out-of-band edits). | Runtime State Inventory | If the live RPC drifted, the hardening migration's `CREATE OR REPLACE` would silently overwrite an undocumented variant. Verify the live RPC before patching. |
| A4 | `key_version` is a plain integer counter (1, 2, ...) sufficient for the two-key rotation window D-02 describes, rather than a key-id string. | Pattern 2 | If a future multi-key fleet is anticipated, a string key-id is more robust; for the current two-key window an integer is fine. Low risk. |

## Open Questions

1. **Allowlist vs. advertised SQL schema conflict (HIGH priority — blocks RPC hardening design).**
   - What we know: D-01 locks the FROM-table allowlist to exactly `{documents, document_chunks, folders}`. The current `QUERYABLE_SCHEMA` in `backend/services/sql_service.py` advertises `threads`, `messages`, `documents`, `document_chunks` to the model (NOT `folders`). `[VERIFIED: backend/services/sql_service.py lines 8-41]`
   - What's unclear: Whether the model legitimately queries `threads`/`messages` today (e.g., "how many conversations do I have?"). If so, the D-01 allowlist would break that behavior. Conversely `folders` is in the allowlist but not advertised.
   - Recommendation: The planner should either (a) reconcile D-01's allowlist to match the actually-used surface — likely `{documents, document_chunks, folders, threads, messages}` minus anything truly unused — and update `QUERYABLE_SCHEMA` to match, OR (b) confirm with the user that dropping `threads`/`messages` from the SQL tool is acceptable. Treat as a discuss-phase clarification, since it touches a locked decision (D-01). The security goal (exclude `user_api_keys`) is satisfied either way; the question is only which legitimate tables stay.

2. **SEC-02 probe layer — unit (mockable) vs. integration (live dev DB) (MEDIUM priority).**
   - What we know: D-05a requires an automated probe driving the SQL tool with `select * from user_api_keys`. The test harness is mock-DB by default (`test_folders_api.py`). The REVOKE is a real Postgres privilege check; an allowlist guard could live either in the RPC (Postgres) or as a backend pre-flight in `execute_sql`.
   - What's unclear: Whether the durable CI gate should hit the live dev Supabase project (needs creds in CI) or assert the allowlist logic at a mockable seam.
   - Recommendation: Put the allowlist check where it is also unit-testable (a pre-flight guard in `execute_sql` OR a pure-Python allowlist helper the RPC mirrors) so the CI probe is deterministic, and add a clearly-marked optional integration test for the REVOKE against dev. The manual dev/prod check at deploy (D-05) covers the live REVOKE. Defense-in-depth means BOTH gates exist regardless of which is unit-tested.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `cryptography` (Fernet/MultiFernet) | crypto_service | ✓ | 46.0.5 | — |
| `pytest` / `pytest-asyncio` | D-05 regression gate | ✓ | 8.4.2 / 0.23.8 | — |
| `supabase` Python client (service-role) | key table I/O | ✓ | 2.13.0 | — |
| Backend `venv` | running tests + key generation | ✓ | `backend/venv/Scripts/python.exe` present | — |
| Dev Supabase project (`.env`) | applying migration 025/026 | ✓ (assumed reachable per dual-env discipline) | — | — |
| `supabase` CLI (`supabase db push`) | applying migrations | UNKNOWN — CLAUDE.md says "dashboard OR `supabase db push`" | — | Apply via Supabase dashboard SQL editor |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** Migration application — if the `supabase` CLI is not installed/linked, apply the migration via the Supabase dashboard SQL editor (the documented alternative). `[CITED: CLAUDE.md line 275]`

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` 8.4.2 (+ `pytest-asyncio` 0.23.8) `[VERIFIED: backend/requirements.txt]` |
| Config file | None detected (no `pytest.ini`/`pyproject.toml [tool.pytest]`); tests rely on `conftest.py` `sys.path` insert. `[VERIFIED: backend/tests/conftest.py lines 2-4]` |
| Quick run command | `cd backend && venv/Scripts/python.exe -m pytest tests/test_crypto_service.py tests/test_config.py -x` |
| Full suite command | `cd backend && venv/Scripts/python.exe -m pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| KEY-02 (crypto) | Encrypt→decrypt round-trip via crypto_service | unit | `pytest tests/test_crypto_service.py::test_encrypt_decrypt_roundtrip -x` | ❌ Wave 0 |
| KEY-02 (rotation) | Second key decrypts + `.rotate()` re-encrypts | unit | `pytest tests/test_crypto_service.py::test_rotation_decrypts_old_and_reencrypts -x` | ❌ Wave 0 |
| KEY-02 (config) | `KEY_ENCRYPTION_SECRET` default + env override | unit | `pytest tests/test_config.py::test_key_encryption_secret_env_override -x` | ⚠️ extend existing `test_config.py` |
| KEY-02 (storage) | Migration applies; ciphertext-only column; RLS present | manual / SQL | apply `...025` to dev; inspect schema in dashboard | ❌ (manual at dev apply, per D-03/D-05) |
| SEC-02 (allowlist) | `select * from user_api_keys` rejected by allowlist | unit | `pytest tests/test_sql_keys_lockdown.py::test_keys_table_query_blocked -x` | ❌ Wave 0 |
| SEC-02 (REVOKE) | Live `authenticated` role denied SELECT on keys table | integration (optional) / manual | run probe against live dev DB; or verify REVOKE in dashboard | ❌ (manual at dev apply, per D-05) |

### Sampling Rate
- **Per task commit:** `pytest tests/test_crypto_service.py tests/test_config.py -x` (sub-second; crypto + config).
- **Per wave merge:** `pytest tests/test_crypto_service.py tests/test_config.py tests/test_sql_keys_lockdown.py -q` (the full Phase 9 unit set).
- **Phase gate:** Full backend suite green (`pytest tests/ -q`) before `/gsd-verify-work`; PLUS the manual dev-apply checks for migration + REVOKE (D-05 acknowledges manual prod check at deploy).

### Observable signals proving each success criterion
1. **Round-trip (criterion #1):** `decrypt_key(encrypt_key(x)) == x` asserted in pytest; ciphertext `!= x`. Dev+prod parity verified by running the same test with each env's `KEY_ENCRYPTION_SECRET` at the respective apply step.
2. **Ciphertext-only storage (criterion #2):** schema inspection shows `encrypted_key text` + `key_version int`, no plaintext column; a sample inserted row's `encrypted_key` is an opaque Fernet token. RLS policies present (`\d user_api_keys` / dashboard).
3. **SQL-tool unreachable (criterion #3):** `execute_sql(..., "select * from user_api_keys")` returns `success=False`/empty (allowlist unit test); live dev probe returns a permission error (REVOKE). Both gates independently observable.
4. **Rotation (criterion #4):** the rotation unit test proves a token encrypted under key A is decryptable after rotating to `[B, A]` and re-encrypts to a B-decryptable token; the rotation runbook doc exists in the phase folder.

### Wave 0 Gaps
- [ ] `tests/test_crypto_service.py` — covers KEY-02 round-trip + rotation (NEW file).
- [ ] `tests/test_sql_keys_lockdown.py` — covers SEC-02 allowlist probe (NEW file).
- [ ] Extend `tests/test_config.py` — `KEY_ENCRYPTION_SECRET` default + env-override (existing file, add 2 tests mirroring the `chat_max_iterations` pattern).
- [ ] No shared crypto fixture needed — tests self-generate keys via `Fernet.generate_key()` + `monkeypatch.setenv` + `get_settings.cache_clear()`.
- [ ] Framework install: none — pytest already present.
- [ ] (Optional, deferred) live-DB integration test for the REVOKE — gate behind an env flag / marker so CI without DB creds skips it.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth flow changes this phase (key provisioning is Phase 10). |
| V3 Session Management | no | Unchanged. |
| V4 Access Control | yes | Per-user RLS on `user_api_keys` (`auth.uid() = user_id`); table-privilege REVOKE on the SQL-tool role; service-role bypass only server-side. |
| V5 Input Validation | yes | `execute_readonly_query` SELECT-only + keyword block + NEW FROM-table allowlist on model-authored SQL. |
| V6 Cryptography | yes | `cryptography` Fernet (AES-128-CBC + HMAC-SHA256) — NEVER hand-rolled; dedicated 32-byte master key per env; MultiFernet rotation with `key_version`. |
| V8 Data Protection | yes | Ciphertext-only at rest; plaintext exists only transiently in backend memory; master key separated from the ciphertext store (env vs DB). |

### Known Threat Patterns for this stack (FastAPI + Supabase + Text-to-SQL agent)

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt-injected SQL exfiltrates the keys table | Information Disclosure | `REVOKE SELECT ... FROM authenticated` (privilege precedes RLS) + positive FROM-table allowlist in the RPC (D-01). `[VERIFIED: postgresql.org]` |
| DB dump leaks usable keys | Information Disclosure | App-layer Fernet; master key held only in env/Fly, never in the DB. A dump yields ciphertext only. |
| Master-key compromise with no rotation path | Tampering / Information Disclosure | MultiFernet + `key_version`; documented rotation runbook; dedicated per-env key (no reuse of JWT/Supabase secrets). |
| Returning the key (cipher or plain) to a client | Information Disclosure | No Phase 9 endpoint selects the key column; future status endpoints return booleans/labels only (Phase 10). |
| Cross-env key reuse (dev key in prod) | Information Disclosure | Distinct `KEY_ENCRYPTION_SECRET` per env (D-04); prod value generated only at deploy. |

> **Out of scope for Phase 9 (do not implement here):** the `sk-or-v1-...` regex scrub for logs/SSE (backend) is **Phase 11**; the Sentry frontend scrub is **Phase 10**. `[CITED: REQUIREMENTS.md traceability; CONTEXT.md deferred]`

## Sources

### Primary (HIGH confidence)
- Installed `cryptography 46.0.5` — empirical verification of `Fernet.generate_key()` length (44), `MultiFernet` encrypt-first/decrypt-any, and `.rotate()` re-encrypt. `[VERIFIED: venv/Scripts/python.exe run]`
- `backend/config.py` — `Settings` + `@lru_cache get_settings()` + `ENV_FILE` dual-env override; empty-default secret pattern. `[VERIFIED: read]`
- `backend/database.py` — service-role `get_supabase()` client (bypasses RLS). `[VERIFIED: read]`
- `backend/auth.py` — confirms `cryptography`/JWT usage (dep present). `[VERIFIED: read]`
- `backend/services/sql_service.py` — `execute_sql` → `execute_readonly_query` RPC; `QUERYABLE_SCHEMA` advertises threads/messages/documents/document_chunks. `[VERIFIED: read]`
- `supabase/migrations/20240301000015_execute_readonly_query.sql` — SECURITY DEFINER, SELECT/WITH-only, keyword block (incl. grant/revoke), `SET LOCAL role='authenticated'`, subquery wrap, row limit. `[VERIFIED: read]`
- `supabase/migrations/20240301000020_update_rls_policies.sql` + `..._018_create_folders_table.sql` — the `auth.uid() = user_id` / mixed-visibility RLS pattern to mirror. `[VERIFIED: read]`
- `backend/tests/conftest.py`, `test_config.py`, `test_folders_api.py` — fixture wiring, config-test pattern, mock-Supabase pattern. `[VERIFIED: read]`
- PostgreSQL docs — Row Security Policies: table privileges are a prerequisite checked before RLS. `[CITED: https://www.postgresql.org/docs/current/ddl-rowsecurity.html]`
- PyPI — `cryptography` latest 49.0.0; installed 46.0.5. `[VERIFIED: pip index versions cryptography]`

### Secondary (MEDIUM confidence)
- `.planning/research/STACK.md`, `ARCHITECTURE.md`, `PITFALLS.md`, `SUMMARY.md` — milestone-level research (encryption choice, schema shape, Pitfall 2/3/4/5, rotation). `[CITED]`
- `.planning/ROADMAP.md` Phase 9 entry — four success criteria. `[VERIFIED: read]`

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every package verified installed; crypto behavior verified empirically against the exact version.
- Architecture: HIGH — RLS pattern, RPC internals, and service-role path all read directly from code; Postgres privilege/RLS precedence verified against official docs.
- Pitfalls: HIGH — grounded in this repo's actual `execute_readonly_query` + config + test code, plus the postgresql.org precedence confirmation.
- Open Questions: One HIGH-priority conflict (allowlist vs. advertised schema) the planner must reconcile because it touches a locked decision.

**Research date:** 2026-06-18
**Valid until:** 2026-07-18 (stable domain — crypto API and Postgres semantics do not move; the QUERYABLE_SCHEMA reconciliation is the only volatile item and is repo-internal).
