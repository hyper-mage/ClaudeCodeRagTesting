# Phase 12: Model Cache + Catalog - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-22
**Phase:** 12-model-cache-catalog
**Areas discussed:** Catalog scope, Refresh + seed, Popularity source, Response shape

---

## Catalog scope

| Option | Description | Selected |
|--------|-------------|----------|
| Store full, filter on read | Cache full raw catalog (~300+); `?free_only=true` filters server-side; honors MODEL-04 auto-refresh | ✓ |
| Curate subset at cache | Only cache allowlisted subset; smaller but fights MODEL-04 auto-refresh | |
| Full, no server filter | Cache+serve everything raw; frontend does all filtering | |

**User's choice:** Store full, filter on read
**Notes:** One cache serves both Phase 15 picker and Phase 11-deferred demo free-only via server-side `free_only` param.

---

## Refresh + seed

### TTL + failure behavior

| Option | Description | Selected |
|--------|-------------|----------|
| 24h TTL, serve stale | Refresh if >24h; serve stale cache on fetch failure | ✓ |
| 6h TTL, serve stale | Fresher but more OpenRouter calls | |
| 24h TTL, error if empty only | 24h; serve stale except explicit empty-cache error | |

**User's choice:** Option 1 (24h TTL, serve stale) — asked "what does TTL mean?"
**Notes:** Clarified plain-text: TTL = Time To Live = max cache age before refresh triggers. "Serve stale on failure" = return old cache if refresh fetch fails (availability > freshness).

### Seed mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| First-request populate | Empty cache; first GET fetches+stores synchronously; self-heals | |
| Deploy-time seed script | Script populates cache at deploy; fast first call, adds deploy step | |
| Both: seed + first-request fallback | Deploy seeds AND first-request populate as safety net | ✓ |

**User's choice:** Both — deploy seed + first-request populate fallback
**Notes:** Belt-and-suspenders guarantees Success Criterion #1 ("never empty on first request") even if deploy seed skipped.

---

## Popularity source

| Option | Description | Selected |
|--------|-------------|----------|
| config.py constant list | Versioned `POPULAR_MODELS` slug list in config.py; tagged at serve time | ✓ |
| Env var (comma-sep) | Editable per-env without code change; no review trail | |
| DB config table | Runtime-editable; but no admin UI → raw SQL edits; overkill | |

**User's choice:** config.py constant list — with curation informed by artificialanalysis.ai rankings (intelligence/speed/cost).

### Follow-up fork: live AA vs curation guide + popularity field shape

User clarified: **wants live AA integration, but as a separate future phase.** Phase 12 must build the popular-models filter so future AA work plugs in.

| Option | Description | Selected |
|--------|-------------|----------|
| Nullable rank + source | `popularity_rank` (int\|null) + `popularity_source` ('curated' now, 'artificialanalysis' later); no DB/API reshape later | ✓ |
| is_popular bool only | Simple boolean; future AA must add rank column + reshape API | |
| Rank + per-axis scores | rank + intelligence/speed/cost score fields now; most future-proof but over-models pre-spec | |

**User's choice:** Option 1 (nullable rank + source) — keep Option 3 (per-axis scores) as a possible later extension once AA is specced.
**Notes:** Phase 12 fills `rank` from curated config; future AA phase overwrites rank+source. Degrade free-first→alphabetical when rank null (Success Criterion #3).

---

## Response shape

| Option | Description | Selected |
|--------|-------------|----------|
| Computed hints + raw kept | Backend computes `is_free`, `price_per_mtok_*`, `context_length` from defensively-parsed strings; also keeps raw pricing | ✓ |
| Raw passthrough only | Serve raw fields; frontend parses/computes (risks blind float() in JS) | |
| Computed only, drop raw | Smallest payload; loses raw for debugging/future fields | |

**User's choice:** Computed hints + raw kept
**Notes:** Frontend renders only, never recomputes pricing. Defensive parse mandatory (never blind `float()`), locked by Success Criterion #2.

---

## Claude's Discretion

- `model_cache` table shape (row-per-model vs JSON blob), `fetched_at`/staleness column design
- Migration filename (next free = `20240301000030_*.sql`), deploy-seed mechanism details
- `GET /api/models` field names + Pydantic models, per-Mtok math/rounding
- `POPULAR_MODELS` exact location/format, endpoint error taxonomy
- Fetch helper location (extend `budget_service` pattern vs new `model_catalog_service`)

## Deferred Ideas

- **Live artificialanalysis.ai ranking integration** (intelligence/speed/cost at runtime) → own future phase
- **Per-axis popularity score columns** → try after AA phase specced
- **Model picker / browsing UI**, free-first/alphabetical sort rendering, demo free-only picker → Phase 15
- **Default model + per-thread model** (`thread.model`, `user_preferences.default_model`) → Phase 13
