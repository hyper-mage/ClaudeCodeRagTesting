# Phase 12: Model Cache + Catalog - Research

**Researched:** 2026-06-22
**Domain:** Supabase-backed cache of the OpenRouter model catalog + FastAPI read endpoint (lazy TTL refresh, defensive pricing parse, curated popularity)
**Confidence:** HIGH (the OpenRouter schema, auth posture, and pricing format were verified empirically against the live endpoint in this session; codebase patterns read directly from source)

## Summary

Phase 12 ships a **data layer only**: a `model_cache` Supabase table, a `GET /api/models` FastAPI endpoint that serves the cached OpenRouter catalog with computed display hints, lazy refresh-if-stale on read (24h TTL, no scheduler), a deploy-time seed plus first-request-populate safety net, and a curated `POPULAR_MODELS` config constant. No UI (Phase 15).

The single most important finding, verified live this session: **`GET https://openrouter.ai/api/v1/models` is publicly readable with no API key** (returns HTTP 200 with no auth header AND with an invalid bearer token), returns **340 models / ~535 KB**, and **all pricing values are strings in per-token USD** (e.g. `gpt-4o-mini` prompt `"0.00000015"` → `$0.15`/Mtok). The catalog fetch is a near-exact generalization of the existing `budget_service.fetch_model_context_length()` — same endpoint, same synchronous-httpx-inside-async pattern, same swallow-on-failure. [VERIFIED: live curl + python analysis of openrouter.ai/api/v1/models, 2026-06-22]

The free/paid decision is cleaner than feared. Empirically: every `:free`-suffixed model also has `prompt=="0" AND completion=="0"` (no contradictions), there are zero models with `prompt=="0"` but nonzero completion, and a `-1` sentinel exists for variable-priced router models (`openrouter/auto`, `openrouter/fusion`) that must be tagged **not-free** and excluded from Mtok math. The recommended rule is `is_free = id.endswith(":free") OR (prompt=="0" AND completion=="0")`, with all parsing guarded — never blind `float()`.

**Primary recommendation:** Build a new `model_catalog_service.py` (mirroring `budget_service`'s httpx pattern) that fetches + tags + computes hints; a row-per-model `model_cache` table with a shared `fetched_at` staleness marker; a `models.py` router doing refresh-if-stale-on-read with a Postgres advisory lock to prevent thundering-herd double-fetch; `POPULAR_MODELS` as an ordered list constant in `config.py`; seed both via a `backend/scripts/seed_model_cache.py` release-command AND the first-request populate path. Make TTL injectable (`model_cache_ttl_seconds` setting) so MODEL-04 is testable without waiting 24h.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Fetch OpenRouter catalog | API / Backend (`model_catalog_service`) | — | Frontend must NEVER call OpenRouter directly (Success Criterion #1); server owns the outbound httpx call |
| Free/paid tagging + Mtok/context hints | API / Backend | — | D-10/D-11: backend computes, frontend renders only; defensive parse must not run client-side |
| Popularity marking | API / Backend (`config.POPULAR_MODELS`) | — | D-06: curated config constant matched at serve time; no DB/admin UI |
| Catalog persistence + staleness | Database / Storage (`model_cache` table) | API (read/write) | D-05: data in Postgres survives Fly suspend / cold starts; process memory does not |
| Lazy refresh-if-stale | API / Backend (`models.py` router) | Database (advisory lock) | D-03: no scheduler; refresh is triggered on the read path; DB lock coordinates concurrency |
| Serve to client / `?free_only` filter | API / Backend | — | D-02: server-side filter; one cache serves picker + demo free-only |
| Picker rendering / sort | Frontend (Phase 15) | — | OUT OF SCOPE this phase — Phase 12 only guarantees the data supports free-first/alphabetical |

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Store the **full raw OpenRouter catalog** (~300+ models, 340 live) in `model_cache`. Do NOT curate/subset at cache time — subsetting fights MODEL-04. New models flow in on refresh with zero allowlist edits.
- **D-02:** **Filter on read, server-side.** `GET /api/models?free_only=true` returns only free models; default returns the full catalog. One cache serves the Phase 15 picker AND the Phase 11-deferred demo free-only need. No client-side free/paid recomputation.
- **D-03:** **Lazy refresh-if-stale on read, 24h TTL.** Each `GET /api/models` checks cache age; if older than 24h, fetch fresh + re-store before responding; else serve as-is. **No in-process scheduler / background worker** (Fly suspend would kill it).
- **D-04:** **Serve stale on refresh failure.** If the OpenRouter fetch fails during a stale-triggered refresh, serve the existing (stale) cache rather than erroring — availability > freshness. (Empty cache == "stale" → triggers the populate path, so first-ever load still fetches.)
- **D-05:** **Seed both ways — deploy seed + first-request populate fallback.** Deploy-time seed populates `model_cache` before traffic; AND the first `GET /api/models` against an empty cache synchronously fetches+stores before responding. The first-request path is the safety net guaranteeing "never empty on first request."
- **D-06:** **`POPULAR_MODELS` lives as a versioned constant in `config.py`** (or a sibling constants module) — a list of OpenRouter model-id slugs. Code-reviewed, ships with deploys, no DB/env round-trip, no admin UI. Backend tags popularity at serve time by matching catalog ids against this list.
- **D-07:** The curated list is **chosen using artificialanalysis.ai rankings** (intelligence / speed / cost) as a **one-time human curation guide** — NOT a runtime call.
- **D-08:** **Forward-compatible popularity shape.** Each model carries `popularity_rank` (int | null) and `popularity_source` (string, `"curated"` in Phase 12). A future AA-integration phase overwrites `rank` + sets `popularity_source = "artificialanalysis"` with no DB/API reshape. The picker (Phase 15) sorts by `popularity_rank`.
- **D-09:** **Graceful degradation when popularity is absent.** When `popularity_rank` is null across the board, default ordering falls back to **free-first, then alphabetical**. Phase 12 guarantees the data supports this; Phase 15 renders the sort.
- **D-10:** **Backend computes display-ready hints; raw pricing kept.** Each entry includes computed `is_free` (bool), `price_per_mtok_prompt` / `price_per_mtok_completion` (float $/Mtok from defensively-parsed strings), and `context_length` (int) — AND retains the raw OpenRouter pricing strings for debugging/future fields. The frontend renders only.
- **D-11:** **Defensive parsing is mandatory.** Free detection uses `pricing.prompt == "0"` AND `pricing.completion == "0"` plus the `:free` id convention; per-Mtok numbers come from a guarded parse — **never a blind `float()`**. Malformed/missing pricing must not crash the endpoint or mis-tag a model.

### Claude's Discretion

Exact `model_cache` table shape (one-row-per-model vs single JSON-blob row + `fetched_at`), the staleness/`fetched_at` column design, migration filename (next free = `20240301000030_*.sql`), the deploy-seed mechanism (seed script vs migration seed vs deploy hook), the `GET /api/models` response field names + Pydantic model, the per-Mtok unit math (× 1e6) and rounding/format, the `POPULAR_MODELS` constant's exact location/format, error taxonomy for the endpoint, and the httpx fetch helper's location (extend `budget_service`'s pattern, or a new `model_catalog_service`) — planner/executor decide, following existing conventions.

### Deferred Ideas (OUT OF SCOPE)

- **Live artificialanalysis.ai ranking integration** — runtime AA pull merged into `/api/models`. Own future phase. Phase 12 ships only the forward-compatible field shape.
- **Per-axis popularity score columns** (separate intelligence / speed / cost). Not modeled now.
- **Model picker / browsing UI**, free-first/alphabetical sort rendering, demo free-only picker → **Phase 15**.
- **Default model + per-thread model selection/persistence** (`thread.model`, `user_preferences.default_model`) → **Phase 13** (MODEL-05, MODEL-06).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MODEL-01 | User can browse a searchable list of available OpenRouter models | `GET /api/models` serves full 340-model catalog from `model_cache`; `?free_only=true` filter (D-02). Search itself is Phase 15 UI; Phase 12 ships the complete dataset. |
| MODEL-02 | Each model is tagged free or paid | `is_free` computed via `id.endswith(":free") OR (prompt=="0" AND completion=="0")`, defensively. Verified: 26 free models live, no contradictions, `-1` sentinel handled. |
| MODEL-03 | Popular models are marked (curated) | `POPULAR_MODELS` ordered list in `config.py` → `popularity_rank` (int|null) + `popularity_source="curated"` at serve time (D-06/D-08). OpenRouter has NO popularity field — confirmed (no such key in 340-model schema). |
| MODEL-04 | List auto-refreshes to pick up new models | Lazy refresh-if-stale on read, 24h TTL, no scheduler (D-03). Testable via injectable `model_cache_ttl_seconds` (set to 0 forces refresh). New model appears on next read after TTL lapse. |
| MODEL-07 | Picker shows context-length and per-Mtok price hints | `context_length` (int, never null in live data) + `price_per_mtok_prompt`/`completion` = `float(per_token_str) * 1_000_000`, guarded (D-10). Verified math: `gpt-4o-mini` → $0.15/$0.60. |
</phase_requirements>

## Standard Stack

This phase uses **only the existing stack** — no new dependencies. CLAUDE.md forbids LangChain; the codebase rule is raw httpx + supabase-py. Everything needed is already installed.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `httpx` | (transitive, used directly) | Outbound `GET /api/v1/models` fetch | Established codebase norm (`budget_service`, `openrouter_service`); synchronous httpx inside async routers |
| `supabase` (supabase-py) | 2.13.0 | Read/write `model_cache` via service-role client (`database.get_supabase()`) | Existing DB access pattern; bypasses RLS server-side |
| `pydantic` | 2.11.1 | `ModelResponse` / catalog response models | CLAUDE.md: "Use Pydantic for structured LLM outputs"; existing `*Response` model convention |
| `pydantic-settings` | 2.9.1 | `POPULAR_MODELS`, `model_cache_ttl_seconds` in `Settings` | Existing `config.py` `@lru_cache get_settings()` pattern |
| `fastapi` | 0.115.12 | `models.py` router | Existing router pattern (`threads.py`, `keys.py`) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | 8.4.2 | Unit tests | Existing test suite (`backend/tests/`) |
| `pytest-asyncio` | 0.23.8 | Async route tests | `asyncio_mode=auto` already configured |
| `unittest.mock` (stdlib) | — | Mock httpx/supabase in tests | Codebase mocks via `monkeypatch` + `MagicMock` (no `respx`/`freezegun` installed) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| New `model_catalog_service.py` | Extend `budget_service.fetch_model_context_length` | `budget_service` is "side-effect free / free of project internals" (its docstring) and does single-model lookup. A catalog fetch that returns ALL models + tagging is a different responsibility — a new service keeps `budget_service` clean. **Recommend new service.** |
| Row-per-model table | Single JSON-blob row + `fetched_at` | Blob row is simplest for "serve whole catalog" but loses SQL-side `?free_only` filtering and per-model indexing. **Recommend row-per-model** (see Pattern 1). |
| Postgres advisory lock for herd control | Accept rare double-fetch | Double-fetch is harmless (idempotent upsert) but wastes a 535 KB fetch under concurrency. Advisory lock is ~5 lines. **Recommend advisory lock** but acceptable to skip if simplicity wins. |
| `freezegun`/`time-machine` for TTL tests | Injectable `model_cache_ttl_seconds` setting | Neither time lib is installed; adding one is a new dep. **Recommend injectable TTL** (set to 0 to force-refresh, large to force-serve-cached). |

**Installation:** None required — all packages already in `backend/requirements.txt`.

**Version verification:** Versions read directly from `backend/requirements.txt` / CLAUDE.md tech-stack block this session — no registry lookup needed since no new packages are added. [VERIFIED: backend/requirements.txt + CLAUDE.md]

## OpenRouter Catalog — Verified Schema (the load-bearing finding)

Fetched live from `https://openrouter.ai/api/v1/models` on 2026-06-22. [VERIFIED: live endpoint, 340 models, 535,415 bytes]

### Top-level shape
```json
{ "data": [ { /* per-model object */ }, ... ] }
```
Single top-level key `data` (a list). No pagination, no popularity field, no "featured" flag. [VERIFIED]

### Per-model fields (union across all 340 models)
```
architecture, benchmarks, canonical_slug, context_length, created,
default_parameters, description, expiration_date, hugging_face_id, id,
knowledge_cutoff, links, name, per_request_limits, pricing, reasoning,
supported_parameters, supported_voices, top_provider
```
Fields this phase needs: **`id`, `name`, `context_length`, `pricing`** (and `canonical_slug` optionally). [VERIFIED]

| Field | Type | Notes (verified live) |
|-------|------|------------------------|
| `id` | str | e.g. `openai/gpt-4o-mini`, `cohere/north-mini-code:free`. Max id length 61. The `:free` suffix is the free convention. |
| `canonical_slug` | str | Versioned slug, e.g. `cohere/north-mini-code-20260617`. NOT the same as `id` for `:free` variants. Use `id` for matching/display. |
| `name` | str | Display name. Max length 54. |
| `context_length` | int | **Never null in live data** (all 340 are int). Range 4,095 – 10,000,000. (Docs say "integer or null" — defend against null anyway.) |
| `pricing` | object | All values **strings**. Sub-keys vary per model (see below). |
| `per_request_limits` | null | Null for all 340 models — ignore. |
| `architecture`, `top_provider`, etc. | object | Not needed this phase; do not store unless cheap. |

### `pricing` object — sub-keys + types (VERIFIED)
Sub-keys present (union): `prompt, completion, image, audio, internal_reasoning, input_cache_read, input_cache_write, web_search`.
**Note:** A `request` key does NOT exist in the current live schema (CONTEXT mentioned it; it is absent now — 0 models have it). Do not depend on it. [VERIFIED: 0/340 models have `pricing.request`]

**All pricing values are strings.** Confirmed for every sub-key. [VERIFIED]

**Unit = per-token USD** (NOT per-Mtok). Proof: `openai/gpt-4o-mini` returns `prompt="0.00000015"`, and `0.00000015 × 1e6 = 0.15`, matching the known public $0.15/Mtok price. [VERIFIED empirically]
> ⚠️ Discrepancy flagged: the OpenRouter docs *page* describes pricing as "per million tokens" and auth as "required." Both describe the **docs' display convention / the authenticated personalized variant**. The **raw public API** returns per-token strings and needs no auth. Trust the empirical values. [VERIFIED: live > docs text]

### Authentication — NOT required for the catalog
`GET /api/v1/models` returns **HTTP 200 with no `Authorization` header** AND **HTTP 200 with a deliberately invalid bearer token**. The public catalog is open. [VERIFIED: curl with no key → 200; curl with `Bearer sk-or-invalid…` → 200]
- **Recommendation:** the server-side catalog fetch should send **no Authorization header** (or pass it only if conveniently available, like `budget_service` does conditionally). Do NOT make the fetch depend on an owner key — that would couple the catalog to key availability and break the "never empty" guarantee. The catalog has no per-user pricing concern for a shared cache.
- Response header `Cache-Control: private, no-store` is present but irrelevant to our own cache TTL.

### Free/paid decision matrix (VERIFIED on live data)
| Condition | Count | Action |
|-----------|-------|--------|
| `id` ends with `:free` | 22 | Free |
| `prompt=="0" AND completion=="0"` | 26 | Free |
| `:free` suffix but pricing NOT both-zero | **0** | (no contradictions — suffix ⊆ price-zero) |
| `prompt=="0"` but `completion!="0"` | **0** | (no split-zero models) |
| price both-zero but NO `:free` suffix | 4 | Free — `openrouter/owl-alpha`, `google/lyria-3-pro-preview`, `google/lyria-3-clip-preview`, `openrouter/free` |
| `prompt=="-1"` (sentinel) | 4 | **NOT free** — variable-priced routers: `openrouter/auto`, `openrouter/fusion`, `openrouter/pareto-code`, `openrouter/bodybuilder` |

**Recommended rule:** `is_free = id.endswith(":free") OR (prompt=="0" AND completion=="0")` → yields **26 free models**. The `-1` sentinel naturally fails this (it's neither `:free` nor `"0"`), so routers are correctly paid/variable. [VERIFIED]

### Per-Mtok math (VERIFIED)
```
price_per_mtok = float(per_token_string) * 1_000_000   # only when parseable AND >= 0
```
- `gpt-4o-mini`: prompt `"0.00000015"` → `$0.15`/Mtok; completion `"0.0000006"` → `$0.60`/Mtok. [VERIFIED]
- Guard: `-1` sentinel → return `None` (don't show a price). Missing/null/malformed string → `None`. Never `float()` blindly.
- 95 distinct prompt-price strings; **no scientific notation** in current data, **one negative** (`-1`). Decimal-string `float()` is safe *inside a try/except*.

## Architecture Patterns

### System Architecture Diagram
```
                          ┌─────────────────────────────────────────┐
  Browser (Phase 15 UI)   │  GET /api/models[?free_only=true]        │
        │                 │  (frontend reads ONLY here, never OR)    │
        ▼                 └─────────────────────────────────────────┘
  ┌──────────────┐                         │
  │ models.py    │  (1) read model_cache + max(fetched_at)
  │ router       │─────────────────────────────────────────► ┌──────────────┐
  │ (FastAPI)    │                                            │ model_cache  │
  │              │  (2) stale? (age > TTL  OR  empty)         │ (Supabase    │
  │              │      │                                     │  Postgres)   │
  │              │      ├─ NO  → serve cached rows ───────────│  row/model   │
  │              │      │                                     │  + fetched_at│
  │              │      └─ YES → try advisory-lock + refresh  └──────┬───────┘
  │              │                  │                                │ upsert
  │              │                  ▼                                │
  │              │           ┌──────────────────┐                   │
  │              │           │ model_catalog_   │  GET (no auth)     │
  │              │           │ service.fetch()  │──────────────────► openrouter.ai
  │              │           │ httpx, 10s tmout │  ◄── 340 models    /api/v1/models
  │              │           └────────┬─────────┘     535 KB        (PUBLIC)
  │              │                    │ on success: upsert rows + stamp fetched_at
  │              │                    │ on FAILURE (D-04): log + serve existing stale rows
  │              │  (3) tag+compute at serve time:                  │
  │              │      is_free, price_per_mtok_*, context_length,  │
  │              │      popularity_rank (match POPULAR_MODELS),     │
  │              │      popularity_source="curated"                 │
  │              ▼                                                  │
  │        ModelResponse[]  (Pydantic, render-ready)               │
  └──────────────┘                                                 │
                                                                   │
  Deploy seed: backend/scripts/seed_model_cache.py ────────────────┘
  (Fly release_command / manual; populates BEFORE traffic — belt; first-request = suspenders)
```

### Recommended Project Structure
```
backend/
├── routers/
│   └── models.py                  # NEW: GET /api/models, refresh-if-stale orchestration
├── services/
│   └── model_catalog_service.py   # NEW: fetch_catalog() httpx + tag_model()/compute_hints() pure fns
├── scripts/
│   └── seed_model_cache.py        # NEW: deploy-time seed (mirrors seed_default_kb.py shape)
├── models/
│   └── schemas.py                 # ADD: ModelResponse, ModelsListResponse
├── config.py                      # ADD: POPULAR_MODELS, model_cache_ttl_seconds
└── main.py                        # ADD: app.include_router(models.router)
supabase/migrations/
└── 20240301000030_create_model_cache.sql   # NEW
```

### Pattern 1: `model_cache` table — row-per-model + shared `fetched_at`
**What:** One row per model (PK = `model_id`), each row carries the raw catalog fields + a `fetched_at` timestamp stamped on every refresh write.
**When to use:** This phase. Row-per-model wins over a single JSON-blob row because it allows SQL-side `?free_only` filtering, indexing, and per-model upsert without read-modify-write races.
**Staleness check:** `SELECT max(fetched_at) FROM model_cache` (or `count==0` → empty → treat as stale per D-05). The whole table shares one logical fetch time because every refresh rewrites all rows in one batch.
```sql
-- Source: synthesized from migration 20240301000025 (RLS pattern) + 20240301000029 (additive) conventions
CREATE TABLE model_cache (
  model_id         TEXT PRIMARY KEY,                  -- OpenRouter `id` (e.g. openai/gpt-4o-mini)
  name             TEXT NOT NULL,
  context_length   INTEGER,                           -- nullable-defensive (live data always int)
  pricing          JSONB NOT NULL,                    -- raw OpenRouter pricing strings (D-10 keeps raw)
  is_free          BOOLEAN NOT NULL DEFAULT false,    -- precomputed at write OR compute at serve (pick one)
  raw              JSONB,                             -- optional: full raw model object for future fields
  fetched_at       TIMESTAMPTZ NOT NULL DEFAULT now() -- staleness marker, restamped every refresh
);

-- GLOBAL shared catalog — NOT user-scoped. Read-only to clients; only service-role writes.
ALTER TABLE model_cache ENABLE ROW LEVEL SECURITY;

-- Public read: every authenticated user sees the same catalog (shared, no per-user rows).
CREATE POLICY "Anyone can read model catalog"
  ON model_cache FOR SELECT
  USING (true);

-- No INSERT/UPDATE/DELETE policy for `authenticated` → RLS denies client writes by default.
-- The service-role backend (database.get_supabase()) bypasses RLS and owns all writes.
```
> **RLS posture (research question #3):** This is a GLOBAL shared table, the mirror image of `user_api_keys` (which was strictly own-row). Catalog has no secrets and is identical for every user, so the SELECT policy is `USING (true)` (or even leave RLS enabled with only a permissive SELECT). Writes happen exclusively through the service-role client which bypasses RLS — so **no write policy is needed** and omitting one is the safe default (clients cannot write). This matches the codebase norm: backend writes via service-role, frontend only ever reads (and here, reads via the backend endpoint, not Supabase directly). [CITED: migration 20240301000025 RLS pattern; ASSUMED that frontend will not query `model_cache` over supabase-js — it reads via `GET /api/models` per Success Criterion #1]

### Pattern 2: Refresh-if-stale-on-read with thundering-herd guard
**What:** On each read, compute staleness; if stale, acquire a Postgres **transaction-level advisory lock** (`pg_try_advisory_xact_lock`) before fetching. Only the lock winner fetches; losers fall through to serve the (about-to-be-or-still) cached rows.
**When to use:** Stateless FastAPI + Supabase where two concurrent reads could both see stale and both fetch 535 KB.
**Why advisory lock over alternatives:** No new table, no extra round-trips beyond one RPC, naturally released at transaction end (or connection close — handles crashes). `pg_try_advisory_lock` is non-blocking: losers immediately proceed to serve cached data (availability > freshness, aligns with D-04).
```python
# Source: synthesized — Postgres pg_try_advisory_xact_lock + supabase-py RPC pattern.
# Run via a tiny SQL RPC (execute_readonly_query is SELECT-only / locked down, so add a
# dedicated SECURITY DEFINER function or call from the service-role client).
LOCK_KEY = 0x6d6f64656c  # arbitrary stable int64 ("model")

def refresh_if_stale(db) -> list[dict]:
    rows = db.table("model_cache").select("*").execute().data
    newest = max((r["fetched_at"] for r in rows), default=None)
    if rows and not _is_stale(newest):          # within TTL → serve as-is
        return rows
    # stale or empty → try to become the single refresher
    got_lock = db.rpc("try_model_cache_lock", {"key": LOCK_KEY}).execute().data
    if not got_lock:
        return rows                              # someone else is refreshing; serve what we have
    try:
        fresh = fetch_catalog()                  # httpx GET, may raise
        _upsert_catalog(db, fresh)               # batch upsert + restamp fetched_at
        return db.table("model_cache").select("*").execute().data
    except Exception as e:                        # D-04: serve stale on failure
        logger.warning("model_cache refresh failed, serving stale: %s", e)
        return rows
```
> **Simpler acceptable fallback (no lock):** because `_upsert_catalog` is an idempotent upsert keyed on `model_id`, a double-fetch produces the correct end state — just wasteful. If the planner wants minimum surface area, skip the lock and accept rare duplicate fetches. The lock is the *recommended* but not *mandatory* refinement. [ASSUMED: advisory lock is over-engineering risk vs benefit — flagged for planner judgment]

### Pattern 3: Tag + compute at serve time (pure functions)
**What:** Keep `model_catalog_service` parsing pure and unit-testable: `tag_is_free(model) -> bool`, `price_per_mtok(price_str) -> float | None`, `popularity_for(model_id, popular_list) -> (rank, source)`. The router composes them into `ModelResponse`.
**When to use:** Always — pure functions are how `budget_service` is structured (its docstring: "side-effect free") and how the test suite mocks (no I/O in the math).
```python
# Source: synthesized from verified pricing format + D-11 defensive rule
def price_per_mtok(per_token: object) -> float | None:
    """Guarded per-Mtok conversion. Returns None for missing/sentinel/malformed."""
    if not isinstance(per_token, str):
        return None
    try:
        v = float(per_token)            # decimal strings only in live data; no sci-notation
    except (TypeError, ValueError):
        return None
    if v < 0:                            # -1 sentinel (openrouter/auto etc.)
        return None
    return round(v * 1_000_000, 4)

def tag_is_free(model: dict) -> bool:
    if str(model.get("id", "")).endswith(":free"):
        return True
    p = model.get("pricing") or {}
    return p.get("prompt") == "0" and p.get("completion") == "0"
```

### Pattern 4: Deploy seed via release command (least-fragile)
**What:** A `backend/scripts/seed_model_cache.py` (mirroring `seed_default_kb.py`) run as a Fly **release command** or a one-off `fly ssh console` after deploy, honoring `ENV_FILE` so it targets the right Supabase env.
**Why not a migration-embedded seed:** Migrations run via Supabase `db push` against the DB only — they cannot make an httpx call to OpenRouter (Postgres has no outbound HTTP). A SQL seed would have to hardcode 340 models, going instantly stale and fighting MODEL-04. **A script that calls the live API is the only seed that stays current.** [VERIFIED: migrations are pure SQL; the catalog must be fetched at runtime, not baked into SQL]
**Why the first-request populate is still needed:** Fly suspend + the deploy seed being skippable means the runtime safety net (D-05) is the real guarantee. The first `GET /api/models` against an empty table fetches synchronously (empty == stale). The deploy seed is an optimization to avoid a slow first request, not the correctness guarantee.

### Anti-Patterns to Avoid
- **Blind `float(pricing.prompt)`:** crashes on `-1`/missing/future non-numeric. Always guard (D-11). [VERIFIED: `-1` exists live]
- **In-process scheduler / `asyncio` background task / APScheduler:** Fly free-tier suspends the machine on idle → the timer dies and never fires. Explicitly OUT OF SCOPE (REQUIREMENTS.md line 80). Refresh MUST be read-triggered.
- **Frontend calling OpenRouter directly:** violates Success Criterion #1. Frontend reads only `GET /api/models`.
- **Subsetting/curating the cache at write time:** breaks MODEL-04 (new models would need allowlist edits). Store ALL 340 (D-01).
- **Storing only a JSON blob row:** loses SQL-side `?free_only` filter and forces read-modify-write. Use row-per-model.
- **Coupling the fetch to an owner API key:** the catalog is public; requiring a key risks an empty cache when no key is configured. Fetch unauthenticated.
- **Caching `get_settings()` won't auto-pick-up a changed TTL mid-process:** `@lru_cache` means env-var TTL changes need a process restart — fine for config, but tests must construct `Settings()` fresh or `monkeypatch` the value (the existing `test_config.py` pattern).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Outbound catalog fetch | Custom retry/backoff HTTP client | `httpx.get(..., timeout=10)` + `raise_for_status`, swallow-on-failure (D-04) | Exactly `budget_service.fetch_model_context_length`'s proven shape |
| Cache persistence | Custom file/in-memory cache | `model_cache` Supabase table | In-process cache dies on Fly suspend (D-05); Postgres survives |
| Staleness / TTL scheduling | Background thread / cron / APScheduler | Read-triggered `fetched_at` age check | Fly suspend kills timers (REQUIREMENTS line 80) |
| Concurrency control | Custom mutex / Redis lock | Postgres `pg_try_advisory_xact_lock` (optional) | DB-native, auto-released, no new infra; idempotent upsert makes even no-lock correct |
| Per-Mtok math | Hand-rolled decimal parsing of arbitrary formats | Guarded `float(str) * 1e6` | Live data is plain decimal strings (no sci-notation); guard handles the `-1` sentinel |
| Response validation | Manual dict shaping | Pydantic `ModelResponse` | CLAUDE.md mandates Pydantic; existing `*Response` convention |

**Key insight:** This phase is almost entirely a *composition* of patterns already in the codebase (the httpx fetch from `budget_service`, the service-role table access from `keys.py`, the RLS migration from `user_api_keys`, the router shape from `threads.py`, the seed script from `seed_default_kb.py`). The only genuinely new reasoning is the defensive pricing parse and the refresh-if-stale orchestration — both small, both verified above.

## Common Pitfalls

### Pitfall 1: The `-1` pricing sentinel mis-tagged as free or crashing Mtok math
**What goes wrong:** `openrouter/auto` and 3 other router models return `prompt="-1"` / `completion="-1"` (variable pricing). A naive `prompt=="0"` check correctly excludes them from free, but `float("-1") * 1e6 = -1000000` would display a nonsense negative price.
**Why it happens:** OpenRouter uses `-1` to mean "price determined at routing time," not a real price.
**How to avoid:** In `price_per_mtok`, return `None` for any `v < 0`. The frontend renders "—" / "variable" for null prices.
**Warning signs:** Negative prices in the UI; `openrouter/auto` showing as free.
[VERIFIED: 4 models with `-1` live]

### Pitfall 2: Trusting the docs' "auth required / per-Mtok" over the live API
**What goes wrong:** Implementing the fetch with a mandatory owner key (breaks when no key set) or dividing prices by 1e6 the wrong way.
**Why it happens:** The OpenRouter docs *page* describes the authenticated/display variant; the raw public API differs.
**How to avoid:** Fetch unauthenticated; treat pricing as **per-token** (`× 1e6` to get per-Mtok). Both confirmed empirically this session.
**Warning signs:** Prices off by 6 orders of magnitude; empty catalog when no owner key configured.
[VERIFIED: live endpoint behavior contradicts docs text]

### Pitfall 3: Full-catalog payload size and Fly cold-start latency
**What goes wrong:** First request after a cold start (empty cache) does a synchronous 535 KB fetch + DB upsert of 340 rows before responding — adds seconds to that one request. Serving the full raw catalog over the wire each read is ~535 KB if you echo everything.
**Why it happens:** D-05 first-request populate is synchronous by design; the raw catalog is large.
**How to avoid:** (a) Store + serve only the needed fields (id, name, context_length, pricing, computed hints) — trimming description/architecture drops the response to **~65 KB** (verified: id+name+ctx+pricing = 65,154 bytes). (b) The deploy seed (Pattern 4) pre-warms the cache so the cold-start first-request usually hits a populated table. (c) The 10s httpx timeout bounds the worst case.
**Warning signs:** First-request latency spikes; large `/api/models` responses.
[VERIFIED: 535 KB full vs 65 KB trimmed]

### Pitfall 4: `context_length` assumed always present
**What goes wrong:** `model["context_length"]` used as int when docs say it can be null.
**Why it happens:** Live data has it for all 340, but the documented type is "integer or null."
**How to avoid:** Defensive `model.get("context_length")` → store nullable; the Pydantic field is `int | None`.
**Warning signs:** `KeyError`/validation error on a future model with null context.
[VERIFIED: 0 null in current data, but docs allow null — defend anyway]

### Pitfall 5: Stale-serve correctness when refresh partially fails
**What goes wrong:** A refresh that fetches successfully but fails mid-upsert could leave the table in a mixed old/new state, or a failed fetch after deleting old rows leaves an empty table.
**Why it happens:** Non-atomic delete-then-insert.
**How to avoid:** Use **upsert keyed on `model_id`** (never delete-all-then-insert), and only restamp `fetched_at` after a fully successful fetch+write. On fetch failure, touch nothing and serve existing rows (D-04). Optionally handle models that disappeared from OpenRouter by upserting-present + leaving absent rows (they'll just be stale; acceptable for v1).
**Warning signs:** Briefly empty catalog after a deploy; duplicate-key errors.
[ASSUMED: upsert-not-replace is the safe write strategy — standard practice, not separately verified against a partial-failure repro]

## Code Examples

### Catalog fetch (generalizing the verified `budget_service` pattern)
```python
# Source: backend/services/budget_service.py:83-106 (verified pattern) + live schema
import httpx, logging
logger = logging.getLogger(__name__)

def fetch_catalog() -> list[dict]:
    """GET the full OpenRouter model catalog. Public endpoint — no auth required.
    Raises on non-2xx so the caller can decide to serve stale (D-04)."""
    resp = httpx.get("https://openrouter.ai/api/v1/models", timeout=10)
    resp.raise_for_status()
    return resp.json().get("data", [])
```

### Popularity tagging from the curated config list
```python
# Source: synthesized from D-06/D-08 + config.py Settings pattern
# config.py:
POPULAR_MODELS: list[str] = [          # ordered: index 0 == most popular → rank 0
    "anthropic/claude-3.7-sonnet",     # curated from artificialanalysis.ai (one-time guide, D-07)
    "openai/gpt-4o-mini",
    "google/gemini-2.0-flash-001",
    # ... executor finalizes the list against live ids at build time
]
model_cache_ttl_seconds: int = 86_400  # 24h (D-03); injectable for tests (MODEL-04)

# serve-time tagging:
def popularity_for(model_id: str, popular: list[str]) -> tuple[int | None, str]:
    try:
        return popular.index(model_id), "curated"   # rank = position; source per D-08
    except ValueError:
        return None, "curated"                       # not popular → null rank, degrade (D-09)
```

### `GET /api/models` router skeleton
```python
# Source: synthesized from backend/routers/threads.py + keys.py conventions
from fastapi import APIRouter, Depends
from auth import get_user_id
from database import get_supabase
from models.schemas import ModelResponse

router = APIRouter(prefix="/api/models", tags=["models"])

@router.get("", response_model=list[ModelResponse])
async def list_models(free_only: bool = False, user_id: str = Depends(get_user_id)):
    db = get_supabase()
    rows = refresh_if_stale(db)               # Pattern 2: serve-or-refresh, never empty (D-05)
    models = [build_model_response(r) for r in rows]   # tag + compute hints (D-10/D-11)
    if free_only:                             # D-02: server-side filter
        models = [m for m in models if m.is_free]
    return models
```
> **Auth note:** `Depends(get_user_id)` matches the codebase norm (all routers require auth). The catalog itself is non-secret, but gating it behind auth is consistent and harmless. Confirm with the planner whether the picker needs it pre-auth (it shouldn't — Phase 15 picker is post-login). [ASSUMED: endpoint stays auth-gated like every other router]

### Pydantic response model
```python
# Source: synthesized from models/schemas.py *Response convention
from pydantic import BaseModel

class ModelResponse(BaseModel):
    id: str
    name: str
    context_length: int | None = None
    is_free: bool
    price_per_mtok_prompt: float | None = None     # None for -1 sentinel / missing
    price_per_mtok_completion: float | None = None
    popularity_rank: int | None = None             # D-08 forward-compatible
    popularity_source: str = "curated"             # D-08; future "artificialanalysis"
    pricing: dict                                  # D-10: raw OpenRouter strings retained
```

## Runtime State Inventory

Not a rename/refactor phase — this is greenfield additive (new table, new router, new service). No existing runtime state is renamed or migrated. Section omitted per template guidance.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pricing.request` per-request fee field | Absent from current `/api/v1/models` response | Observed 2026-06-22 | Don't read/depend on `pricing.request`; CONTEXT's mention is stale |
| Auth-required model list (older OpenRouter docs phrasing) | Public catalog, no auth needed | Verified 2026-06-22 | Fetch unauthenticated; don't couple to owner key |
| Background scheduler for refresh | Lazy TTL refresh-on-read | Project decision (Fly suspend) | REQUIREMENTS line 80 — anti-feature |

**Deprecated/outdated:**
- The OpenRouter docs page (`/docs/api/api-reference/models/get-models`) text stating "Authorization required" and "per million tokens" describes the display/authenticated variant — the raw public API differs (verified empirically). Trust the live values.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Frontend will read the catalog only via `GET /api/models`, never query `model_cache` over supabase-js directly | RLS posture (Pattern 1) | If the SPA queries `model_cache` directly, the permissive `USING (true)` SELECT policy is what allows it — still safe (non-secret data), but confirm intent. Success Criterion #1 says frontend reads only via backend. Low risk. |
| A2 | Advisory-lock herd control is optional polish; idempotent upsert makes no-lock correct (just wasteful) | Pattern 2 | If the planner skips the lock, rare concurrent stale reads double-fetch 535 KB. Harmless to correctness. Low risk. |
| A3 | Upsert-keyed-on-`model_id` (never delete-all) is the safe refresh write strategy | Pitfall 5 | If a delete-then-insert is used instead, a mid-write failure could briefly empty the catalog. Mitigated by recommending upsert. Low risk. |
| A4 | `GET /api/models` stays auth-gated (`Depends(get_user_id)`) like every other router | Router skeleton | If the Phase 15 picker must render pre-login, the endpoint may need to be public. Decide in planning. Low risk (picker is post-login). |
| A5 | The curated `POPULAR_MODELS` ids will be finalized by the executor against live ids at build time | Popularity tagging | A stale/wrong id simply yields `popularity_rank=None` for that model (degrades gracefully per D-09). Self-healing. Very low risk. |
| A6 | Storing a trimmed field set (id/name/context_length/pricing + computed) rather than the full raw model is acceptable | Pitfall 3 | If a future field is needed without re-fetch, the optional `raw` JSONB column (Pattern 1) covers it. D-10 only requires raw *pricing* be kept. Low risk. |

## Open Questions

1. **Precompute `is_free` at write time vs compute at serve time?**
   - What we know: D-10 says backend computes; D-11 says defensive. Both storage-time and serve-time satisfy it.
   - What's unclear: storing `is_free` as a column enables a SQL `WHERE is_free` for `?free_only` (faster, less Python); computing at serve keeps the table a pure mirror.
   - Recommendation: store `is_free` as a column (enables SQL-side `?free_only` filter per D-02) AND retain raw pricing; compute the Mtok hints at serve time (cheap). Planner's call.

2. **How is the deploy seed actually invoked on Fly?**
   - What we know: `seed_default_kb.py` exists as a manual script; `ENV_FILE` switches envs; `fly.toml` has no `release_command` currently.
   - What's unclear: whether to add a `[deploy] release_command` to `fly.toml` (runs every deploy, idempotent — fine) or run the seed manually post-deploy.
   - Recommendation: add an idempotent `release_command` running `python -m scripts.seed_model_cache`, OR rely solely on the first-request populate (D-05 makes the seed optional for correctness). The first-request path is the real guarantee; the deploy seed is a latency optimization.

3. **Should models that vanished from OpenRouter be pruned from the cache?**
   - What we know: upsert-present leaves stale absent rows.
   - What's unclear: whether a deprecated model lingering in the picker is a problem (Phase 13 already handles a pinned-to-deprecated-model fallback at send time).
   - Recommendation: don't prune in v1 (simplest); a model that 404s at chat time is handled by Phase 11's 402/429/error surfacing + Phase 13's deprecation fallback. Revisit if it causes picker clutter.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| OpenRouter `/api/v1/models` | Catalog fetch | ✓ (HTTP 200, public, no auth) | live 2026-06-22 | Serve stale cache (D-04); first-ever load has no fallback but endpoint is up |
| Supabase Postgres (dev `.env`) | `model_cache` table read/write | ✓ (existing project) | — | — |
| Supabase Postgres (prod `.env.prod`) | Prod migration 030 + seed | ✓ (existing project) | — | Apply via `db push` after `migration repair` per MEMORY note |
| `httpx` / `supabase` / `pydantic` | Service + router | ✓ (in requirements.txt) | as listed | — |
| `pytest` + `pytest-asyncio` | Tests | ✓ | 8.4.2 / 0.23.8 | — |
| `freezegun` / `time-machine` | TTL time-travel tests | ✗ (not installed) | — | Injectable `model_cache_ttl_seconds` (set 0 to force refresh) — no time lib needed |
| `respx` (httpx mock lib) | Mock outbound fetch in tests | ✗ (not installed) | — | `monkeypatch` the `fetch_catalog`/`httpx.get` symbol (codebase norm — see `mock_stream_chat_completion`) |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** `freezegun`/`respx` — both avoided by using injectable TTL + `monkeypatch` (the established test approach; no new test deps needed).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 + pytest-asyncio 0.23.8 (`asyncio_mode=auto`) |
| Config file | `backend/pytest.ini` (`testpaths=tests`, `--strict-markers`, `integration` marker) |
| Quick run command | `cd backend && python -m pytest tests/test_model_catalog.py -x` |
| Full suite command | `cd backend && python -m pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MODEL-02 | `:free` suffix tagged free | unit | `pytest tests/test_model_catalog.py::test_free_by_suffix -x` | ❌ Wave 0 |
| MODEL-02 | `prompt==0 AND completion==0` tagged free | unit | `pytest tests/test_model_catalog.py::test_free_by_zero_price -x` | ❌ Wave 0 |
| MODEL-02 | `-1` sentinel NOT free, NOT mis-priced | unit | `pytest tests/test_model_catalog.py::test_sentinel_not_free -x` | ❌ Wave 0 |
| MODEL-02 | malformed/missing pricing doesn't crash (defensive) | unit | `pytest tests/test_model_catalog.py::test_pricing_parse_guards -x` | ❌ Wave 0 |
| MODEL-07 | per-Mtok math (`gpt-4o-mini` → 0.15/0.60) | unit | `pytest tests/test_model_catalog.py::test_price_per_mtok -x` | ❌ Wave 0 |
| MODEL-07 | context_length surfaced; null-safe | unit | `pytest tests/test_model_catalog.py::test_context_length_nullsafe -x` | ❌ Wave 0 |
| MODEL-03 | popularity rank from `POPULAR_MODELS`; absent → null | unit | `pytest tests/test_model_catalog.py::test_popularity_tagging -x` | ❌ Wave 0 |
| MODEL-04 | stale (TTL lapsed/empty) triggers refresh; fresh model appears | unit (injected TTL=0 + monkeypatched fetch) | `pytest tests/test_model_catalog.py::test_refresh_when_stale -x` | ❌ Wave 0 |
| MODEL-04 | within-TTL serves cache without fetch | unit | `pytest tests/test_model_catalog.py::test_serve_cached_within_ttl -x` | ❌ Wave 0 |
| MODEL-04/D-04 | fetch failure during refresh serves stale | unit | `pytest tests/test_model_catalog.py::test_serve_stale_on_fetch_failure -x` | ❌ Wave 0 |
| MODEL-01/D-02 | `?free_only=true` filters server-side | unit (route) | `pytest tests/test_models_api.py::test_free_only_filter -x` | ❌ Wave 0 |
| MODEL-01/D-05 | empty cache populates on first read (never empty) | unit | `pytest tests/test_models_api.py::test_first_request_populate -x` | ❌ Wave 0 |
| config | `model_cache_ttl_seconds` default 86400 + env override | unit | `pytest tests/test_config.py::test_model_cache_ttl_default -x` | ❌ Wave 0 (extend existing file) |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/test_model_catalog.py tests/test_models_api.py -x`
- **Per wave merge:** `cd backend && python -m pytest`
- **Phase gate:** Full suite green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `backend/tests/test_model_catalog.py` — pure-function tests (tagging, Mtok math, popularity, refresh-if-stale with injected TTL + monkeypatched fetch). Covers MODEL-02/03/04/07.
- [ ] `backend/tests/test_models_api.py` — route-level tests (`?free_only`, first-request populate, serve-stale-on-failure). Covers MODEL-01/04 + D-02/D-04/D-05.
- [ ] Extend `backend/tests/test_config.py` — `model_cache_ttl_seconds` default + env override (existing file pattern).
- [ ] Capture a small **fixture** of real OpenRouter models (e.g. `tests/fixtures/openrouter_models_sample.json` with `gpt-4o-mini`, a `:free` model, an `openrouter/auto` `-1` model, one missing-pricing edge) so tests run offline without hitting the live API. The session already verified the exact shapes to fixture.
- Framework install: none — pytest already present.

## Security Domain

`security_enforcement` is not set to `false` in config — section included. This phase handles a **non-secret, globally-shared public catalog**; the security surface is small.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Catalog is non-secret; endpoint reuses existing `get_user_id` dep (no new auth) |
| V3 Session Management | no | No session state introduced |
| V4 Access Control | yes (light) | `model_cache` RLS: permissive SELECT (`USING (true)`), NO client write policy → service-role-only writes. No per-user data. |
| V5 Input Validation | yes | `free_only` query param is a typed bool (FastAPI coercion); OpenRouter response parsed defensively (D-11) — malformed upstream data must not crash the endpoint |
| V6 Cryptography | no | No secrets, no crypto in this phase (unlike Phase 9) |

### Known Threat Patterns for FastAPI + Supabase + outbound httpx
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed/hostile upstream catalog payload crashes endpoint (DoS) | Denial of Service | Defensive parse (D-11): guarded `float`, `.get()` everywhere, `int | None` fields; never crash on a bad model row |
| Catalog table writable by a client → poisoned model list | Tampering | RLS: no INSERT/UPDATE/DELETE policy for `authenticated`; only service-role writes (bypasses RLS by design) |
| SSRF via the outbound fetch | — | URL is a hardcoded constant (`https://openrouter.ai/api/v1/models`); no user input flows into it |
| Secret leakage | Information Disclosure | N/A — catalog has no secrets; the fetch sends no Authorization header. (Contrast: `openrouter_service.exchange_code` never logs its body because it holds a key; here there is nothing to scrub, but mirror the no-log-body httpx hygiene anyway.) |
| Oversized response amplification | Denial of Service | Serve trimmed fields (~65 KB) not the full 535 KB raw; 10s httpx timeout bounds the fetch |

## Sources

### Primary (HIGH confidence)
- **Live `https://openrouter.ai/api/v1/models`** (curl + python analysis, 2026-06-22) — 340 models, 535 KB, all pricing strings, per-token USD unit, public/no-auth (200 with bad key), `:free` ⊆ price-zero, `-1` sentinel, `request` key absent, `context_length` always int in current data. The authoritative source for this phase's schema claims.
- **`backend/services/budget_service.py:83-106`** — `fetch_model_context_length()`: the canonical httpx-GET-models pattern (timeout, `raise_for_status`, swallow-on-failure, conditional auth header).
- **`backend/services/openrouter_service.py`** — `exchange_code()`: outbound OpenRouter httpx hygiene (timeout, raise_for_status, never-log-body).
- **`backend/routers/threads.py`, `backend/routers/keys.py`** — router + service-role table-access conventions.
- **`supabase/migrations/20240301000025_create_user_api_keys.sql`** — RLS migration pattern (own-row vs the global pattern this phase inverts).
- **`backend/config.py`, `backend/tests/test_config.py`** — Settings + env-override test pattern (basis for `model_cache_ttl_seconds`).
- **`backend/scripts/seed_default_kb.py`** — idempotent seed-script shape for the deploy seed.
- **`Dockerfile`, `fly.toml`** — deploy context (suspend on idle, no release_command currently, `ENV_FILE` env switching).

### Secondary (MEDIUM confidence)
- **OpenRouter docs** via WebSearch (`openrouter.ai/docs/api/api-reference/models/get-models`, `/docs/api/reference/overview`) — confirmed pricing is string + USD + "0 means free" + `:free` = "always free, low rate limits". NOTE: the docs page's "auth required / per-million-tokens" phrasing was **contradicted by the live API** and is treated as the display/authenticated variant.

### Tertiary (LOW confidence)
- None relied upon for load-bearing claims. (Search surfaced costgoat.com pricing aggregators — not used.)

## Metadata

**Confidence breakdown:**
- OpenRouter schema / pricing / auth: **HIGH** — verified empirically against the live endpoint this session, not from training data.
- Free/paid tagging rule: **HIGH** — decision matrix run against all 340 live models; zero contradictions found.
- Standard stack: **HIGH** — no new deps; all read directly from `requirements.txt`/codebase.
- Architecture (table shape, refresh-if-stale, seed strategy): **MEDIUM-HIGH** — patterns synthesized from verified codebase conventions; advisory-lock and seed-invocation specifics flagged as planner-discretion (A2, Open Q2).
- Pitfalls: **HIGH** — `-1` sentinel, payload size, docs-vs-live discrepancy all empirically verified.

**Research date:** 2026-06-22
**Valid until:** ~2026-07-22 for codebase patterns (stable); OpenRouter catalog *contents* change continuously (that's the point of MODEL-04), but the *schema* (string pricing, `:free` convention, public endpoint) has been stable and is low-churn — re-verify the schema if implementation slips past ~30 days.
