# Phase 12: Model Cache + Catalog - Context

**Gathered:** 2026-06-22
**Status:** Ready for planning

<domain>
## Phase Boundary

A Supabase-backed cache of the **OpenRouter model catalog**, served to the frontend via a backend `GET /api/models` endpoint — with free/paid tagging, curated popularity marking, and context-length + per-Mtok price hints. The cache **refreshes lazily** (refresh-if-stale on read; no in-process scheduler — Fly suspend would kill it), is **seeded at deploy**, is **never empty on first request**, and **survives Fly suspend / cold starts** (data lives in Supabase, not in-process).

**In scope (MODEL-01, MODEL-02, MODEL-03, MODEL-04, MODEL-07):**
- New `model_cache` Supabase table + migration (next free number = **030**).
- `GET /api/models` backend endpoint serving the full catalog from `model_cache`; frontend reads **only** via the backend, **never** OpenRouter directly.
- Lazy **refresh-if-stale** on read (24h TTL); seed-at-deploy + first-request-populate fallback so the table is never empty.
- Free vs paid tagging from **defensively-parsed string pricing** (`pricing.prompt == "0"` AND `pricing.completion == "0"`, plus the `:free` id convention) — never blind `float()`.
- Curated **popularity** marking from a config allowlist (OpenRouter has no popularity field), with **forward-compatible rank shape** for a future live ranking integration.
- Backend-computed display hints: `is_free`, per-Mtok price (`price_per_mtok_prompt` / `price_per_mtok_completion`), `context_length`.
- Optional server-side `?free_only=true` filter (serves the Phase 11-deferred demo free-only need + Phase 15 picker from one cache).

**Out of scope (later phases):**
- **Picker / browsing UI** — the searchable model picker, free-first/alphabetical sort rendering, demo free-only picker → **Phase 15** (this phase ships the data layer + API; "joins the rest only at the picker UI").
- **Default model + per-thread model** (`thread.model`, `user_preferences.default_model`, persistence/UI) → **Phase 13** (MODEL-05, MODEL-06).
- **Live artificialanalysis.ai ranking integration** (intelligence/speed/cost axes pulled at runtime) → **own future phase** (see Deferred). Phase 12 only ships the curated static list + a rank shape that future work fills.
- Usage/cost display, balance, settings/key-state UX → **Phase 14**.

</domain>

<decisions>
## Implementation Decisions

### Catalog scope & filtering (MODEL-01)
- **D-01:** **Store the full raw OpenRouter catalog** (~300+ models) in `model_cache`. Do **not** curate/subset at cache time — subsetting fights MODEL-04 ("newly added models appear automatically"). New models flow into the cache on refresh with zero allowlist edits.
- **D-02:** **Filter on read, server-side.** `GET /api/models?free_only=true` returns only free models; default (no param) returns the full catalog. One cache serves both the Phase 15 picker AND the Phase 11-deferred demo free-only need. No client-side free/paid recomputation.

### Refresh strategy & seeding (MODEL-04, Success Criterion #1 & #4)
- **D-03:** **Lazy refresh-if-stale on read, 24h TTL.** Each `GET /api/models` checks cache age; if older than 24h, fetch fresh from OpenRouter and re-store before responding; if within 24h, serve as-is. **No in-process scheduler / background worker** (Fly suspend would kill it). TTL = "Time To Live" = max cache age before a refresh is triggered.
- **D-04:** **Serve stale on refresh failure.** If the OpenRouter fetch fails during a stale-triggered refresh (network/5xx/timeout), serve the existing (stale) cached catalog rather than erroring — availability > freshness. (Empty cache is treated as "stale" → triggers the populate path in D-05, so first-ever load still fetches.)
- **D-05:** **Seed both ways — deploy seed + first-request populate fallback.** A deploy-time seed populates `model_cache` before traffic; AND the first `GET /api/models` against an empty cache synchronously fetches+stores before responding (empty == stale). The first-request path is the safety net guaranteeing "never empty on first request" even if the deploy seed is skipped/fails. Data in Supabase → survives Fly suspend + cold starts.

### Popularity curation (MODEL-03, Success Criterion #3)
- **D-06:** **`POPULAR_MODELS` lives as a versioned constant in `config.py`** (or a sibling constants module) — a list of OpenRouter model-id slugs. Code-reviewed, ships with deploys, no DB/env round-trip, no admin UI needed (CLAUDE.md: "no admin UI"). Backend tags popularity at serve time by matching catalog ids against this list.
- **D-07:** The curated list is **chosen using artificialanalysis.ai rankings** (intelligence / speed / cost) as a **one-time human curation guide** — NOT a runtime call. (Live AA integration is a separate future phase — see Deferred.)
- **D-08:** **Forward-compatible popularity shape.** Each model carries `popularity_rank` (int | null) and `popularity_source` (string, `"curated"` in Phase 12). Phase 12 fills `rank` from the curated config order; a future AA-integration phase **overwrites** `rank` + sets `popularity_source = "artificialanalysis"` with **no DB/API reshape**. The picker (Phase 15) sorts by `popularity_rank`.
- **D-09:** **Graceful degradation when popularity is absent** (Success Criterion #3): when `popularity_rank` is null across the board (or popularity data unavailable), default ordering falls back to **free-first, then alphabetical**. Phase 12 guarantees the data supports this; the picker (Phase 15) renders the sort.

### Response shape & price hints (MODEL-02, MODEL-07, Success Criterion #2)
- **D-10:** **Backend computes display-ready hints; raw pricing kept.** Each `GET /api/models` entry includes computed `is_free` (bool), `price_per_mtok_prompt` / `price_per_mtok_completion` (float $ per million tokens, derived from defensively-parsed pricing strings), and `context_length` (int) — **and also retains the raw OpenRouter pricing strings** for debugging / future fields without a re-fetch. The frontend **renders only**, never parses/recomputes pricing.
- **D-11:** **Defensive parsing is mandatory** (Success Criterion #2): free detection uses `pricing.prompt == "0"` AND `pricing.completion == "0"` plus the `:free` id convention; per-Mtok numbers come from a guarded parse of the string fields — **never a blind `float()`** (malformed/missing pricing must not crash the endpoint or mis-tag a model). Mirrors the codebase's existing "never `float()` blindly" pricing rule.

### Claude's Discretion
- Exact `model_cache` table shape (one-row-per-model vs single JSON-blob row + `fetched_at`), the staleness/`fetched_at` column design, migration filename (next free = `20240301000030_*.sql`), the deploy-seed mechanism (seed script vs migration seed vs deploy hook), the `GET /api/models` response field names + Pydantic model, the per-Mtok unit math (× 1e6) and rounding/format, the `POPULAR_MODELS` constant's exact location/format, error taxonomy for the endpoint, and the httpx fetch helper's location (extend `budget_service.fetch_model_context_length`'s pattern, or a new `model_catalog_service`) — planner/executor decide, following existing conventions.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` — Phase 12 entry (goal, 4 success criteria, requirements MODEL-01/02/03/04/07; depends-on Phase 8, parallelizable with 9–11, joins at Phase 15 picker)
- `.planning/REQUIREMENTS.md` — MODEL-01, MODEL-02, MODEL-03, MODEL-04, MODEL-07 definitions + traceability (lines 20–26, 96–102)

### Prior-phase foundations (what this phase consumes / coordinates with)
- `.planning/phases/11-per-request-key-model-resolution-chat-loop-seam/11-CONTEXT.md` — deferred to Phase 12: free/paid tagging + free-only catalog filter (D-08 demo notes); `demo_fallback_model` free `:free` slug consumes this catalog; three-tier model resolution (Phase 13 lights up `thread.model` / `user_preferences`)
- `.planning/research/ARCHITECTURE.md` §"Model resolution order" + per-request client construction (model-selection context this catalog feeds)
- `.planning/research/STACK.md` — OpenRouter integration conventions

### Code to reuse / mirror
- `backend/services/budget_service.py` — `fetch_model_context_length()` (lines 83–106): the established synchronous-`httpx` call to `https://openrouter.ai/api/v1/models` (`data[]` with `id`, `context_length`, `pricing`) + swallow-on-failure pattern. The catalog fetch reuses this endpoint + httpx pattern.
- `backend/services/openrouter_service.py` — `exchange_code()`: the codebase norm for outbound OpenRouter httpx calls (timeout, `raise_for_status`); note its SECURITY rule (never log response bodies — N/A here since model catalog has no secrets, but mirror the httpx hygiene).
- `backend/config.py` — `Settings` (pydantic-settings, `@lru_cache get_settings()`); `llm_base_url = "https://openrouter.ai/api/v1"` (line 56), `demo_fallback_model` (line 41), `model_context_length` fallback (line 126). Add `POPULAR_MODELS` + any TTL setting here.
- `backend/database.py` — service-role `get_supabase()` for reading/writing `model_cache` (table is global/non-user-scoped — confirm RLS posture: catalog is shared, not per-user).
- `supabase/migrations/` — sequential numbering `20240301000NNN_*.sql`; latest applied = `20240301000029_add_usage_to_messages.sql` (Phase 11) → **next free = 030**.
- `backend/routers/` — `chat.py` / `threads.py` / `documents.py` router pattern (FastAPI `Depends()` for `user_id`/`settings`); new `models.py` router mirrors these.

### External (reference only — NOT a Phase 12 runtime dependency)
- `https://openrouter.ai/api/v1/models` — the catalog source (`data[]`: `id`, `name`, `context_length`, `pricing.prompt`/`pricing.completion` as **strings**, `:free` id convention)
- `https://artificialanalysis.ai` — human curation guide for the `POPULAR_MODELS` list (intelligence/speed/cost rankings). **Not** called at runtime in Phase 12.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`budget_service.fetch_model_context_length()`** — already GETs `https://openrouter.ai/api/v1/models`, iterates `resp.json()["data"]`, reads per-model `context_length`. The catalog fetcher generalizes this (read `id` + `pricing` + `context_length` for ALL models, not just one lookup). Same httpx + timeout + swallow-on-failure shape.
- **`config.py` `Settings` + `@lru_cache get_settings()`** — home for `POPULAR_MODELS` and any TTL/staleness config. Owner/global config is fine to cache here (unlike per-request keys).
- **FastAPI router pattern (`backend/routers/*`)** — `Depends()` injection, Pydantic response models suffixed `Response`; new `models.py` router + `ModelResponse`/catalog models mirror this.
- **Supabase service-role client (`database.py get_supabase()`)** — writes/reads `model_cache` server-side.

### Established Patterns
- Migrations sequentially numbered `20240301000NNN_*.sql`; next free = **030**.
- Outbound OpenRouter calls use **synchronous httpx** inside async routers (budget_service / openrouter_service norm), `raise_for_status`, bounded timeout.
- Pricing fields from OpenRouter are **strings** (`"0"`, `"0.0000004"`); the codebase rule is **never blind `float()`** — guard + the `:free` convention (locked by Success Criterion #2 and Phase 11 precedent).
- pydantic-settings config; dual Supabase envs (`.env` dev / `.env.prod` prod) — see [[project_dual_supabase_envs]]. Deploy seed must run against the correct env. See [[prod_byok_secrets_applied]] for prod deploy mechanics (Fly + CF build main, push master:main).

### Integration Points
- `GET /api/models` (new `models.py` router) → `model_cache` table (read) → stale-check → conditional OpenRouter fetch (refresh) → tag free/paid + popularity + compute hints → Pydantic response.
- `model_cache` (Supabase) ← deploy seed + first-request populate; survives Fly suspend (data in Postgres, not process memory).
- Catalog data → consumed later by Phase 15 picker UI and Phase 11's `demo_fallback_model` free-slug selection (free-only filter).
- `POPULAR_MODELS` (config) → popularity tagging at serve time → `popularity_rank`/`popularity_source` fields → Phase 15 picker sort; future AA phase overwrites these fields.

</code_context>

<specifics>
## Specific Ideas

- Popular-models list curated from **artificialanalysis.ai** rankings (intelligence / speed / cost) as a one-time human guide — user explicitly wants this informing the curated set, with a **live AA integration to follow in a later phase**. Phase 12's popularity field shape (`popularity_rank` + `popularity_source`) must accommodate that future work with no reshape.
- Per-axis AA scores (separate intelligence / speed / cost columns) are a **possible later extension** to try once the AA phase is specced — don't model them now (avoid over-modeling before the AA phase exists), but keep `popularity_rank` + `popularity_source` extensible toward them.
- `free_only` server-side filter is the seam that serves both the Phase 15 picker's free-tier view AND the Phase 11-deferred demo free-only requirement from one cache.
- "Never empty on first request" is guaranteed by the **belt-and-suspenders** seed (deploy seed + first-request populate), not by either alone.

</specifics>

<deferred>
## Deferred Ideas

- **Live artificialanalysis.ai ranking integration** — backend pulls AA rankings (intelligence / speed / cost) at runtime and merges them into `/api/models`, overwriting `popularity_rank` + setting `popularity_source = "artificialanalysis"`. New external dependency + new capability → **its own future phase** (user explicitly scoped it out of Phase 12). Phase 12 ships the forward-compatible field shape so this plugs in cleanly.
- **Per-axis popularity score columns** (separate intelligence / speed / cost) — try after the AA phase is specced, if the picker benefits from multi-axis sort. Not modeled in Phase 12.
- **Model picker / browsing UI**, free-first/alphabetical sort rendering, demo free-only picker → **Phase 15**.
- **Default model + per-thread model selection/persistence** (`thread.model`, `user_preferences.default_model`) → **Phase 13** (MODEL-05, MODEL-06).

None of these block Phase 12 — discussion stayed within the catalog/cache data-layer scope.

</deferred>

---

*Phase: 12-model-cache-catalog*
*Context gathered: 2026-06-22*
