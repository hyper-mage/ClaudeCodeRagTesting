---
quick_id: 260910-lcm
type: execute
plan: 01
wave: 1
depends_on: []
autonomous: true
complexity: medium
files_modified:
  - backend/services/model_catalog_service.py
  - backend/routers/models.py
  - backend/config.py
  - backend/tests/test_model_catalog.py
  - backend/tests/test_models_api.py
user_setup: []

must_haves:
  truths:
    - "A model carrying benchmarks.artificial_analysis.intelligence_index can receive popularity_rank from that score, with popularity_source == 'artificialanalysis'"
    - "A model with no AA score still gets its curated POPULAR_MODELS rank with popularity_source == 'curated'"
    - "A model in neither gets popularity_rank None / popularity_source 'curated' (unchanged D-08/D-09 behavior)"
    - "Ordering is identical across two consecutive requests over the same rows (deterministic tiebreak)"
    - "A malformed/absent/wrong-typed benchmarks blob degrades to the curated fallback and NEVER raises"
    - "The Popular section in the existing frontend stays bounded (a small ranked set, not the whole catalog)"
    - "No migration, no TTL change, no lifespan hook, no extra HTTP fetch — the 24h refresh_if_stale path carries the AA scores for free"
  artifacts:
    - path: "backend/services/model_catalog_service.py"
      provides: "intelligence_index() reader, aa_ranking() ordering, AA-aware popularity_for(), aa_ranks-aware build_model_response()"
      contains: "def aa_ranking"
    - path: "backend/routers/models.py"
      provides: "Per-request AA ordering computed once from rows and passed into build_model_response"
      contains: "aa_ranking(rows)"
    - path: "backend/config.py"
      provides: "Refreshed POPULAR_MODELS fallback list verified against the live catalog on 2026-09-10"
      contains: "POPULAR_MODELS"
  key_links:
    - from: "backend/routers/models.py::list_models"
      to: "backend/services/model_catalog_service.py::aa_ranking"
      via: "computed once per request from the full row set, passed down per row"
      pattern: "aa_ranking\\(rows\\)"
    - from: "backend/services/model_catalog_service.py::build_model_response"
      to: "backend/services/model_catalog_service.py::popularity_for"
      via: "aa_ranks keyword forwarded through"
      pattern: "popularity_for\\("
---

# Auto-update model popularity_rank from the live OpenRouter AA benchmark index

**Complexity:** ⚠️ **Medium** — 3 backend files + 2 test files. No migration, no new dependency, no frontend change. The single non-obvious part is that rank is a *cross-catalog position* while `build_model_response` is *per-row*, so the ordering must be computed once per request and threaded down.

<objective>
`popularity_rank` is currently sourced only from the hand-curated `POPULAR_MODELS` list in `config.py`, last verified 2026-06-23 and now stale. Make rank derive primarily from the live Artificial Analysis intelligence index that OpenRouter already ships inside each catalog entry, keeping the curated list as the fallback for models with no AA score.

Purpose: the ranking self-updates every 24h with zero operator action, because the existing `refresh_if_stale` path already re-fetches the catalog and `_to_cache_row` already persists the full upstream object under `raw` — the benchmarks are ALREADY in the `model_cache` table today.

Output: AA-primary / curated-fallback ranking, a refreshed curated list, and test coverage for both paths plus the malformed-blob degradation.
</objective>

<execution_context>
@C:/Users/56kbps/Desktop/Projects/VibeCoded Projects/AI Automators Masterclass/claude-code-agentic-rag-masterclass/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@./CLAUDE.md
@backend/services/model_catalog_service.py
@backend/routers/models.py
@backend/config.py
@backend/tests/test_model_catalog.py
@backend/tests/test_models_api.py
</context>

<verified_facts>
Measured against `https://openrouter.ai/api/v1/models` (public, no auth) on 2026-09-10 during planning. Do not re-derive these from memory; re-run the commands if you need to confirm.

- 437 models in the catalog; 132 carry `benchmarks.artificial_analysis.intelligence_index`. **Do not hardcode either count** — it drifts.
- Exact upstream shape:
  `"benchmarks": {"design_arena": [], "artificial_analysis": {"intelligence_index": 52.8, "coding_index": 76.9, "agentic_index": 51.5}}`
  `design_arena` can be an empty **list**. Many models omit `benchmarks` entirely. Assume any sub-value can be the wrong type.
- `_to_cache_row` already stores `"raw": model`. **No migration. No extra HTTP fetch.**
- `build_model_response` accepts BOTH shapes: a raw catalog object (id under `id`, `benchmarks` top-level) and a `model_cache` row (id under `model_id`, benchmarks nested under `raw`). The new benchmarks reader must handle both the same way `model.get("id") or model.get("model_id")` already does for the id.
- **`:batch` duplicates are pervasive and would poison the ranking.** Every top model has an identical-score `:batch` twin, so an unfiltered top-20 is really only 10 distinct models. Exclude ids ending `:batch` from the AA ordering.
- Ties in `intelligence_index` are real (e.g. two entries at 53.4). A deterministic tiebreak is mandatory or ranks shuffle between page loads.
- Live top-12 non-`:batch` at planning time (a sanity reference, NOT something to hardcode): `anthropic/claude-fable-5.1` (53.4), `openai/gpt-6-astra` (52.8), `anthropic/claude-opus-5` (50.7), `anthropic/claude-fable-5` (49.7), `openai/gpt-5.6-sol` (47.1), `z-ai/glm-5.3` (44.9), `x-ai/grok-4.6` (44.4), `moonshotai/kimi-k3` (43.8), `openai/gpt-5.6-terra` (42.3), `anthropic/claude-opus-4.8` (42.0), `z-ai/glm-5.3-flash` (41.9), `google/gemini-3.8-flash` (41.2).
- **There is NO `anthropic/claude-sonnet-5`.** The newest Sonnet is `anthropic/claude-sonnet-4.6`. Never write a sonnet-5 slug.
- Slugs re-verified present on 2026-09-10: `anthropic/claude-opus-5`, `anthropic/claude-sonnet-4.6`, `anthropic/claude-haiku-4.5`, `openai/gpt-5.4`, `openai/gpt-5.2`, `openai/gpt-5.1`, `google/gemini-3.1-pro-preview`, `google/gemini-3.5-flash`, `deepseek/deepseek-v4-pro`, `x-ai/grok-4.6`, `meta-llama/llama-4-maverick`.
- Re-verify any slug with:
  `python -c "import json,urllib.request; ids={m['id'] for m in json.load(urllib.request.urlopen('https://openrouter.ai/api/v1/models'))['data']}; print('anthropic/claude-opus-5' in ids)"`

Caller audit (grepped `backend/` and `backend/tests/`): the ONLY caller of `build_model_response` outside its own module is `routers/models.py::list_models`. The ONLY caller of `popularity_for` is `build_model_response` plus `test_model_catalog.py::test_popularity_tagging`. `scripts/seed_model_cache.py` imports only `_to_cache_row` and `fetch_catalog` — untouched by this change.
</verified_facts>

<design_decisions>
Four decisions the executor must implement as stated — they are the reason this plan exists.

**DD-1 — New params are OPTIONAL keywords, not required positionals.**
`popularity_for(model_id, popular, aa_ranks=None)` and `build_model_response(model, aa_ranks=None)`. Rationale: `test_popularity_tagging` calls `popularity_for("vendor/second", popular)` with two positional args and must keep passing untouched; several `test_models_api.py` paths reach `build_model_response` indirectly. Defaulting to `None` means every existing call site keeps its current curated-only behavior, so this is a strictly additive change. Chosen over a required positional specifically to avoid a breaking signature change.

**DD-2 — The ordering is computed ONCE per request in the router, never per row.**
Rank is a position across the whole catalog; a per-model pure function cannot know it. `list_models` already holds `rows` from `refresh_if_stale(db)`, so it calls `aa_ranking(rows)` once and passes the resulting `dict[str, int]` into each `build_model_response(row, aa_ranks=...)` call. `popularity_for` stays side-effect-free and pure — it *receives* the ordering, it never computes it.

**DD-3 — Deterministic tiebreak: `intelligence_index` DESC, then `model_id` ASC.**
Two models at 53.4 must land in the same order on every request or the Popular section reshuffles between page loads. Sort key: `(-score, model_id)`.

**DD-4 — The AA ordering is CAPPED at the top `AA_RANK_LIMIT = 12`, and curated fallback ranks are OFFSET below it.**

Read this one carefully — it is the non-obvious consequence that would otherwise ship as a UX regression.

`frontend/src/components/ModelSelector.tsx:198` builds the "Popular" section as `rows.filter(m => m.popularity_rank != null)` with **no cap**, and `ModelHint` renders a "Popular" chip on every model whose rank is non-null. Today exactly 10 models have a non-null rank. If every AA-scored model received a rank, the Popular section would balloon to ~132 rows and ~132 models would wear a "Popular" chip — the section would become a near-duplicate of "All models" and stop meaning anything. Frontend changes are out of scope for this task, so the bound is enforced **backend-side** and the frontend contract (`rank != null` ⇒ Popular) is preserved byte-for-byte.

Concretely:
- Only the top `AA_RANK_LIMIT` non-`:batch` AA models get an AA rank (`0..11`, source `"artificialanalysis"`).
- Models below that cutoff fall through to the curated list exactly like an unscored model. This is intentional and useful: at planning time `claude-sonnet-4.6` (30.5), `gemini-3.5-flash` (33.0), `haiku-4.5` (17.6) and `llama-4-maverick` (9.3) all score below the cutoff, so the curated list is what keeps those popular workhorses in the Popular section.
- Curated ranks are **offset by the number of AA-ranked models** so the two sources form ONE continuous ordering instead of colliding at rank 0. With 12 AA models, curated indexes become `12, 13, 14, ...`. Without an offset the AA #1 and the curated #1 would both be rank 0 and the frontend's ascending sort would interleave them unpredictably.
- The offset is `len(aa_ranks)`, so when `aa_ranks` is `None`/empty the offset is `0` and behavior is byte-identical to today (this is what keeps `test_popularity_tagging` green).
- Resulting Popular section: at most 12 AA + at most 10 curated, minus overlap ≈ 19 rows. Bounded and deterministic.
- Escape hatch, document it in the constant's docstring: raising or removing `AA_RANK_LIMIT` widens the Popular section proportionally; it is a single-constant change if the product decision later flips.

**Cold-cache note (no action required):** rows cached before OpenRouter began emitting `benchmarks` will have no AA data in `raw` and will simply use the curated fallback until the next 24h refresh restamps them. Self-healing; do not add a backfill.
</design_decisions>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write the failing tests for the AA ranking path (RED)</name>
  <files>backend/tests/test_model_catalog.py, backend/tests/test_models_api.py</files>
  <behavior>
  In `backend/tests/test_model_catalog.py`, append a new section header comment `# --- AA-index popularity (quick 260910-lcm) ---` and these tests. Follow the file's existing norms exactly: import the symbols INSIDE each test body, build inline dicts for hostile inputs (mirroring `test_free_by_zero_price`), and do NOT edit `backend/tests/fixtures/openrouter_models_sample.json` — the shared fixture carries no `benchmarks` key and every existing test depends on that staying true.

  - `test_intelligence_index_both_shapes` — `intelligence_index({"id": "a/b", "benchmarks": {"artificial_analysis": {"intelligence_index": 52.8}}})` returns `52.8`; the `model_cache` row shape `{"model_id": "a/b", "raw": {"benchmarks": {"artificial_analysis": {"intelligence_index": 52.8}}}}` also returns `52.8`.
  - `test_intelligence_index_defensive` — every one of these returns `None` and raises nothing: `{}`; `{"benchmarks": None}`; `{"benchmarks": []}`; `{"benchmarks": "nope"}`; `{"benchmarks": {"design_arena": []}}`; `{"benchmarks": {"artificial_analysis": []}}` (the empty-list-instead-of-dict case); `{"benchmarks": {"artificial_analysis": {"intelligence_index": None}}}`; `{"benchmarks": {"artificial_analysis": {"intelligence_index": "52.8"}}}` (string, not numeric); `{"benchmarks": {"artificial_analysis": {"intelligence_index": True}}}` (bool must not be accepted as an int).
  - `test_aa_ranking_orders_by_index_desc` — given rows for `a/low` (10.0), `a/high` (50.0), `a/mid` (30.0), `aa_ranking` returns `{"a/high": 0, "a/mid": 1, "a/low": 2}`.
  - `test_aa_ranking_tiebreak_is_model_id_asc` — two rows tied at 42.0 with ids `z/model` and `a/model` rank `a/model` → 0 and `z/model` → 1; assert the SAME dict is returned when the input list order is reversed (proves stability across requests).
  - `test_aa_ranking_excludes_batch_variants` — rows for `a/x` (53.4) and `a/x:batch` (53.4) yield a dict containing `a/x` and NOT `a/x:batch`.
  - `test_aa_ranking_respects_limit` — 20 synthetic scored rows with `limit=12` yields exactly 12 entries with ranks `0..11`.
  - `test_aa_ranking_skips_unscored_and_malformed` — a mixed list containing an unscored row, a `None` entry, a non-dict entry, and a row with an empty-string id produces a dict holding only the validly-scored rows, and raises nothing.
  - `test_popularity_for_aa_wins_over_curated` — `popularity_for("vendor/top", ["vendor/top"], aa_ranks={"vendor/top": 0})` returns `(0, "artificialanalysis")`.
  - `test_popularity_for_curated_offset_below_aa` — with `aa_ranks={"x/1": 0, "x/2": 1}` (len 2), `popularity_for("vendor/second", ["vendor/most-popular", "vendor/second"], aa_ranks=aa_ranks)` returns `(3, "curated")` (offset 2 + index 1), and an id in neither returns `(None, "curated")`.
  - `test_popularity_for_default_arg_is_unchanged` — calling with two positional args only still returns `(1, "curated")` for index 1 (guards DD-1: no breaking signature change).
  - `test_build_model_response_threads_aa_ranks` — `build_model_response(row, aa_ranks={"a/high": 0})` on a row whose id is `a/high` returns `popularity_rank == 0` and `popularity_source == "artificialanalysis"`; the same call with no `aa_ranks` argument returns `popularity_source == "curated"`.

  In `backend/tests/test_models_api.py`, add `test_aa_rank_served_end_to_end` — extend a copy of `_cache_rows_from_fixture()` with two extra rows whose `raw` carries an `artificial_analysis.intelligence_index` (a high and a low), serve them through the within-TTL route path used by `test_free_only_filter`, and assert the response body has the high-scoring model at `popularity_rank` 0 with `popularity_source == "artificialanalysis"` while the fixture rows (no benchmarks) still come back with `popularity_source == "curated"`. Build the extra rows locally in the test; do not mutate the shared helper.
  </behavior>
  <action>
  Write the tests described in the behavior block. They MUST fail RED against the current code for the RIGHT reason — an `ImportError` on `intelligence_index` / `aa_ranking` and a `TypeError` on the unexpected `aa_ranks` keyword — not for a typo or a bad mock. Do not touch `model_catalog_service.py`, `routers/models.py`, or `config.py` in this task. Do not edit the shared JSON fixture.
  </action>
  <verify>
    <automated>backend/venv/Scripts/python.exe -m pytest backend/tests/test_model_catalog.py backend/tests/test_models_api.py -p no:dash -q 2>&1 | tail -25</automated>
  </verify>
  <done>The new tests fail with ImportError/TypeError naming the not-yet-existing symbols; the 15 pre-existing `test_model_catalog.py` tests and all `test_models_api.py` tests still pass.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement the AA reader, the capped ordering, and the router wiring (GREEN)</name>
  <files>backend/services/model_catalog_service.py, backend/routers/models.py</files>
  <behavior>All tests from Task 1 pass, and the 15 pre-existing `test_model_catalog.py` tests plus all `test_models_api.py` tests stay green with no edits to them.</behavior>
  <action>
  In `backend/services/model_catalog_service.py`, alongside the existing `CATALOG_URL`, add a module constant `AA_RANK_LIMIT: int = 12` with a docstring/comment stating that it bounds the frontend's uncapped Popular section (`ModelSelector.tsx:198`) and is the single knob to widen it (DD-4).

  Add `intelligence_index(model: dict) -> float | None` in the pure-functions section next to `price_per_mtok`. It reads `model.get("benchmarks")`; if that is not a dict it retries via `model.get("raw")` when `raw` is a dict (covers the `model_cache` row shape). It then requires `artificial_analysis` to be a dict, requires `intelligence_index` to be an `int`/`float` while explicitly rejecting `bool` (bool subclasses int), and returns `float(value)`. Every access is `.get()`-guarded with an `isinstance` check — match the existing `price_per_mtok` / `tag_is_free` defensive posture exactly. It NEVER raises.

  Add `aa_ranking(rows: list[dict], limit: int = AA_RANK_LIMIT) -> dict[str, int]`. It skips non-dict entries, resolves the id via `str(row.get("id") or row.get("model_id") or "")`, skips empty ids, skips ids ending `:batch` (per verified_facts — identical-score batch twins would consume half the slots), skips rows where `intelligence_index` returns `None`, sorts the survivors by `(-score, model_id)` (DD-3), truncates to `limit`, and returns `{model_id: rank}`. Pure and side-effect-free; it NEVER raises on a malformed row set.

  Change `popularity_for` to `popularity_for(model_id: str, popular: list[str], aa_ranks: dict[str, int] | None = None) -> tuple[int | None, str]`. New order of resolution: (1) if `aa_ranks` is a dict containing `model_id`, return `(aa_ranks[model_id], "artificialanalysis")`; (2) otherwise take `offset = len(aa_ranks or {})` and return `(offset + popular.index(model_id), "curated")`; (3) on `ValueError` return `(None, "curated")`. Update the docstring: the source is no longer always `"curated"`, the AA path is now live, and the offset exists so AA and curated ranks form one continuous ordering rather than colliding at 0 (DD-4).

  Change `build_model_response` to `build_model_response(model: dict, aa_ranks: dict[str, int] | None = None) -> dict` and forward `aa_ranks` into `popularity_for`. Keep everything else in that function byte-identical. Update its docstring to say popularity is now AA-primary with a curated fallback and that `aa_ranks` is precomputed by the caller because rank is a cross-catalog position (DD-2).

  In `backend/routers/models.py`, import `aa_ranking` alongside the existing imports, and in `list_models` compute `aa_ranks = aa_ranking(rows)` ONCE after `rows = refresh_if_stale(db)`, then build with `[build_model_response(row, aa_ranks=aa_ranks) for row in rows]`. Extend the module docstring's helper list and the `list_models` docstring numbered flow with the new step, matching the surrounding comment style.

  Add no dependency, no migration, no lifespan hook, no scheduler, no TTL change, no extra HTTP call. Type hints on every param and return; `dict[str, int] | None` union syntax not `Optional`; snake_case; 4-space indent; double quotes; docstrings on every new function.
  </action>
  <verify>
    <automated>backend/venv/Scripts/python.exe -m pytest backend/tests/test_model_catalog.py backend/tests/test_models_api.py -p no:dash -q 2>&1 | tail -15</automated>
  </verify>
  <done>Every test from Task 1 passes; no pre-existing test in either file was modified; `grep -n "aa_ranking(rows)" backend/routers/models.py` matches exactly once.</done>
</task>

<task type="auto">
  <name>Task 3: Refresh the curated fallback list and run the full backend regression</name>
  <files>backend/config.py</files>
  <action>
  Replace the `POPULAR_MODELS` list in `backend/config.py` with slugs verified against the live catalog, and rewrite the comment block above it.

  The comment must now state: (a) the list is the FALLBACK for models with no AA `intelligence_index` and for AA models below the `AA_RANK_LIMIT` cutoff — it is no longer the primary ranking source; (b) `model_catalog_service.aa_ranking` is the primary source and self-updates every 24h via `refresh_if_stale`; (c) ranks from this list are offset below the AA ranks so the two form one continuous ordering; (d) slugs were finalized against the live OpenRouter catalog on **2026-09-10**; (e) the existing self-heal guarantee still holds — a slug that later goes stale yields `popularity_rank` None via the `popularity_for` ValueError path (D-09), never a crash. Delete the now-wrong "Curated using artificialanalysis.ai rankings as a one-time human guide" framing, since AA is now a live input rather than a one-time guide.

  Use this ordered list (every slug re-verified present on 2026-09-10; ordering favors popular workhorses that score BELOW the AA cutoff, since the AA path already covers the top tier):

      "anthropic/claude-opus-5",
      "anthropic/claude-sonnet-4.6",
      "openai/gpt-5.4",
      "google/gemini-3.1-pro-preview",
      "openai/gpt-5.2",
      "anthropic/claude-haiku-4.5",
      "google/gemini-3.5-flash",
      "deepseek/deepseek-v4-pro",
      "openai/gpt-5.1",
      "meta-llama/llama-4-maverick",

  Before writing them, re-verify with the one-liner in verified_facts. If any slug has disappeared since planning, drop it rather than inventing a replacement, and note the drop in the SUMMARY. **Never write `anthropic/claude-sonnet-5` — it does not exist.** Prefer non-`:batch` variants.

  Then run the full backend suite to confirm nothing else regressed (`test_config.py`, `test_key_model_resolution.py`, and `test_deprecated_model_fallback.py` are the likely blast radius for a config-constant change).

  Out of scope, record as an observation in the SUMMARY only — do NOT fix here: `demo_fallback_model` still defaults to `meta-llama/llama-3.3-70b-instruct:free`, which is GONE from the live catalog. Harmless today because `demo_fallback_enabled` defaults OFF.
  </action>
  <verify>
    <automated>backend/venv/Scripts/python.exe -m pytest backend/tests -p no:dash -q 2>&1 | tail -15</automated>
  </verify>
  <done>Full backend suite passes with no new failures versus the pre-change baseline; `POPULAR_MODELS` holds only slugs confirmed live on 2026-09-10; the comment block describes the list's fallback role and carries the 2026-09-10 date.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| OpenRouter catalog → `model_cache.raw` → `build_model_response` | A third-party JSON blob is parsed and its numeric field drives server-computed ordering. Untrusted-shape input crosses here. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-LCM-01 | Denial of Service | `intelligence_index` / `aa_ranking` | mitigate | A malformed `benchmarks` blob (list-instead-of-dict, string score, `None`, bool) must not raise — an unhandled exception in the per-row build would 500 the whole `GET /api/models` and blank the model picker. Guarded via `isinstance` on every access; Task 1 `test_intelligence_index_defensive` and `test_aa_ranking_skips_unscored_and_malformed` are the enforcing gates. |
| T-LCM-02 | Tampering | upstream `intelligence_index` value | accept | OpenRouter is already a trusted supply-chain dependency for the entire catalog (name, pricing, context_length). A poisoned score reorders a display list only — no spend, no auth, no data access. Bounded further by `AA_RANK_LIMIT`. |
| T-LCM-03 | Information Disclosure | `GET /api/models` response | accept | The AA index is public data from a public endpoint; the route is already auth-gated and per-user-agnostic. No new field is exposed — `popularity_rank`/`popularity_source` already ship in `ModelResponse`. |
| T-LCM-SC | Tampering | npm/pip/cargo installs | n/a | **No package installs in this task.** Zero new dependencies; the ranking uses stdlib `sorted` over data already in the cache. No legitimacy checkpoint required. |
</threat_model>

<verification>
1. `backend/venv/Scripts/python.exe -m pytest backend/tests -p no:dash -q` — full suite green.
2. `grep -n "AA_RANK_LIMIT\|def aa_ranking\|def intelligence_index" backend/services/model_catalog_service.py` — all three present.
3. `grep -n "aa_ranking(rows)" backend/routers/models.py` — computed once, in the router, not per row.
4. `grep -v '^#' backend/config.py | grep -c "claude-sonnet-5"` — must be `0` (the non-existent slug never shipped).
5. No migration file added: `git status --short supabase/migrations/` is empty.
6. No frontend file touched: `git status --short frontend/` is empty.
7. `git diff --stat` touches only the five files in `files_modified`.
</verification>

<success_criteria>
- A model with a top-12 AA `intelligence_index` serves `popularity_source == "artificialanalysis"` and a rank in `0..11`.
- A model without one (or below the cutoff) serves `popularity_source == "curated"` with its offset curated index, or `None` when in neither list.
- Repeating the same request over the same rows yields byte-identical ordering (deterministic tiebreak proven by test).
- Every malformed-benchmarks shape from Task 1 degrades to the curated fallback and raises nothing.
- `model_cache_ttl_seconds` is still `86400`; no scheduler, lifespan hook, migration, or new dependency was added.
- The frontend Popular section stays bounded (≤ ~19 rows) with zero frontend edits.
- Full backend suite green.
</success_criteria>

<output>
Create `.planning/quick/260910-lcm-auto-update-model-popularity-rank-from-l/260910-lcm-SUMMARY.md` when done. Record: the final `POPULAR_MODELS` slugs actually shipped (and any dropped at re-verification), the observed `demo_fallback_model` staleness, and confirmation that no migration/frontend file was touched.
</output>
