---
quick_id: 260910-lcm
type: summary
plan: 01
status: complete
completed: 2026-09-10
tasks_completed: 3
tasks_total: 3
key-files:
  modified:
    - backend/services/model_catalog_service.py
    - backend/routers/models.py
    - backend/config.py
    - backend/tests/test_model_catalog.py
    - backend/tests/test_models_api.py
commits:
  - 0b6e5bc
  - cc09481
  - aab64b7
metrics:
  tests_before: 15 (test_model_catalog.py) / 18 (both catalog test files)
  tests_after: 30 (both catalog test files)
  full_suite_before: 326 passed, 2 failed, 7 errors
  full_suite_after: 326 passed, 2 failed, 7 errors
---

# Quick 260910-lcm: Auto-update model popularity_rank from the live OpenRouter AA benchmark index — Summary

`popularity_rank` now derives primarily from the live Artificial Analysis intelligence index that OpenRouter already ships inside each catalog entry, with the hand-curated `POPULAR_MODELS` list demoted to a fallback — so the top of the ranking self-updates every 24h through the existing `refresh_if_stale` path with no operator action, no migration, and no extra HTTP fetch.

## What Shipped

**Task 1 (RED) — `0b6e5bc`**
Twelve new tests appended across `backend/tests/test_model_catalog.py` (11) and `backend/tests/test_models_api.py` (1). Eleven failed RED for exactly the intended reasons — `ImportError: cannot import name 'intelligence_index'`, `ImportError: cannot import name 'aa_ranking'`, `TypeError: popularity_for() got an unexpected keyword argument 'aa_ranks'`, `TypeError: build_model_response() got an unexpected keyword argument 'aa_ranks'`. The twelfth, `test_popularity_for_default_arg_is_unchanged`, passed immediately by design: it is the DD-1 guard asserting the two-positional-arg call keeps byte-identical behavior, so passing before *and* after is the correct outcome. The shared JSON fixture `backend/tests/fixtures/openrouter_models_sample.json` was not touched, and neither was the shared `_cache_rows_from_fixture()` helper — the end-to-end test extends a local copy.

**Task 2 (GREEN) — `cc09481`**
- `AA_RANK_LIMIT: int = 12` added next to `CATALOG_URL`, with a comment documenting that it exists to bound the frontend's uncapped Popular section (`ModelSelector.tsx:198` filters on `popularity_rank != null`) and that it is the single knob to widen it.
- `intelligence_index(model: dict) -> float | None` — reads `benchmarks.artificial_analysis.intelligence_index`, falling back to `model["raw"]["benchmarks"]` for the `model_cache` row shape. Every access is `.get()`-guarded with an `isinstance` check, matching the existing `price_per_mtok` / `tag_is_free` posture. `bool` is rejected explicitly since it subclasses `int`.
- `aa_ranking(rows, limit=AA_RANK_LIMIT) -> dict[str, int]` — skips non-dict entries, empty ids, `:batch` twins and unscored rows; sorts `(-score, model_id)`; truncates to `limit`.
- `popularity_for(model_id, popular, aa_ranks=None)` — AA hit wins; otherwise curated index offset by `len(aa_ranks)`; otherwise `(None, "curated")`.
- `build_model_response(model, aa_ranks=None)` forwards `aa_ranks` through; everything else in that function is unchanged.
- `backend/routers/models.py` computes `aa_ranks = aa_ranking(rows)` once per request after `refresh_if_stale(db)` and threads the map into each row build.

**Task 3 (config refresh + regression) — `aab64b7`**
`POPULAR_MODELS` replaced and its comment block rewritten to describe the list's new fallback role, the AA primary source, the offset, the 2026-09-10 verification date, and the retained D-09 self-heal guarantee. The "Curated using artificialanalysis.ai rankings as a one-time human guide" framing was deleted, since AA is now a live input rather than a one-time guide.

## POPULAR_MODELS Slugs Actually Shipped

All ten planned slugs were re-verified against the live catalog immediately before writing, using a full-catalog membership test (`{m['id'] for m in ...}` over all 437 entries) — never a sliced or truncated listing. **All ten were PRESENT. Nothing was dropped, and nothing was substituted.**

| # | Slug | Membership check |
|---|------|------------------|
| 0 | `anthropic/claude-opus-5` | PRESENT |
| 1 | `anthropic/claude-sonnet-5` | PRESENT |
| 2 | `openai/gpt-5.4` | PRESENT |
| 3 | `google/gemini-3.1-pro-preview` | PRESENT |
| 4 | `openai/gpt-5.2` | PRESENT |
| 5 | `anthropic/claude-haiku-4.5` | PRESENT |
| 6 | `google/gemini-3.5-flash` | PRESENT |
| 7 | `deepseek/deepseek-v4-pro` | PRESENT |
| 8 | `openai/gpt-5.1` | PRESENT |
| 9 | `meta-llama/llama-4-maverick` | PRESENT |

`anthropic/claude-sonnet-5` is confirmed live and IS pinned, exactly as the plan specifies. Verification step 4 (`grep -v '^#' backend/config.py | grep -c "claude-sonnet-5"`) returns `1`; the stricter indented-comment-stripping variant (`grep -v '^\s*#'`) also returns `1`, so the count is satisfied by the actual list entry and not by comment prose.

Both deliberate content choices were preserved: `claude-sonnet-4.6` is NOT also pinned (sonnet-5 supersedes it, and pinning both would burn two of ten fallback slots on one model line), and `claude-opus-5` stays pinned despite holding AA rank 2, as insurance against OpenRouter ever dropping its score.

## Live Behavior Verification

Running the shipped `aa_ranking` against the real catalog produced a result matching the plan's reference exactly:

- 437 models in the catalog, 132 carrying an `intelligence_index`.
- 12 AA ranks produced (`AA_RANK_LIMIT` respected), with zero `:batch` entries.
- Ordering: `claude-fable-5.1` (53.4) → `gpt-6-astra` (52.8) → `claude-opus-5` (50.7) → `claude-fable-5` (49.7) → `gpt-5.6-sol` (47.1) → `glm-5.3` (44.9) → `grok-4.6` (44.4) → `kimi-k3` (43.8) → `gpt-5.6-terra` (42.3) → `claude-opus-4.8` (42.0) → `glm-5.3-flash` (41.9) → `gemini-3.8-flash` (41.2).
- `anthropic/claude-sonnet-5` scores 38.4 and is confirmed NOT in the AA top-12 — validating the plan's reasoning that the curated list is its only route into the Popular section.

Resulting Popular section bound: at most 12 AA + at most 10 curated, minus the opus-5 overlap = 21 rows maximum. Bounded and deterministic, with zero frontend edits.

## Test Results

| Scope | Before | After |
|-------|--------|-------|
| `test_model_catalog.py` | 15 passed | 26 passed |
| `test_model_catalog.py` + `test_models_api.py` | 18 passed | 30 passed |
| Full backend suite | 326 passed, 2 failed, 7 errors | 326 passed, 2 failed, 7 errors |

No pre-existing test in either file was modified. The full-suite failure/error set is byte-identical before and after — same test IDs, no regression.

## Pre-existing Failures (out of scope, NOT introduced here)

Confirmed unrelated to this change and present in the baseline:

- `test_config.py::test_key_encryption_secret_default` — asserts the default is `""` but a real `KEY_ENCRYPTION_SECRET` is set in the local `.env`, so the cached settings carry a live value. Local-environment artifact, nothing to do with `POPULAR_MODELS`.
- 7 errors in `backend/tests/integration/` and `test_record_manager.py` — `fixture 'user_id' not found`. Pre-existing harness gap in the real-DB integration tests.
- `integration/test_thread_shapes.py::test_delete_nonexistent_thread_404` — real-DB integration test, unrelated.

## Observation (recorded only, deliberately NOT fixed)

`backend/config.py:42` — `demo_fallback_model` still defaults to `meta-llama/llama-3.3-70b-instruct:free`, which the membership test confirms is **GONE** from the live catalog. The non-`:free` variant `meta-llama/llama-3.3-70b-instruct` does survive. This is harmless today because `demo_fallback_enabled` defaults to `False`, so the branch that reads the slug never runs. Explicitly out of scope for this task per the plan; flagged here for whoever re-validates the demo-fallback path.

## Deviations from Plan

**1. [Rule 3 - Blocking] Router docstring phrasing adjusted to satisfy the grep verification**

- **Found during:** Task 2
- **Issue:** The plan asked for the module docstring's helper list and the `list_models` numbered flow to be extended with the new step, and separately required `grep -c "aa_ranking(rows)" backend/routers/models.py` to equal `1`. Writing both docstring mentions in the surrounding parallel style (`refresh_if_stale(db)` / `build_model_response(row)`) produced the literal token `aa_ranking(rows)` three times, so the count returned `3`.
- **Fix:** Reworded the two prose mentions to `aa_ranking(cached rows)` and `aa_ranking over the cached rows`, preserving both the documentation content and the parallel style while leaving the literal token to the single code call site.
- **Files modified:** `backend/routers/models.py`
- **Commit:** `cc09481`
- **Verified:** `grep -n "aa_ranking(rows)"` now matches only line 59, `aa_ranks = aa_ranking(rows)`.

No other deviations. No auth gates were hit.

## Invariants Confirmed

- No migration file added — `git status --short supabase/migrations/` empty.
- No frontend file touched — `git status --short frontend/` empty.
- `git diff --stat` spans exactly the five files listed in `files_modified`, nothing else.
- No file deletions in any of the three commits; no untracked files left behind.
- `model_cache_ttl_seconds` unchanged at `86400`. No scheduler, no lifespan/startup hook, no new dependency, no extra HTTP fetch — the ranking sorts data already persisted under `model_cache.raw`.
- No delete-all on `model_cache`; the upsert path was not touched.
- No LangChain / LangGraph. Type hints on every new param and return, `dict[str, int] | None` union syntax, `list[dict]` generics, snake_case, 4-space indent, double quotes, docstrings on every new function.

## Known Stubs

None.

## Threat Flags

None. No new network endpoint, auth path, file access pattern, or schema change was introduced. The one trust boundary in play (OpenRouter catalog JSON → `model_cache.raw` → server-computed ordering) was already in the plan's threat register as T-LCM-01 and is mitigated by `test_intelligence_index_defensive` plus `test_aa_ranking_skips_unscored_and_malformed`, both green.

## Self-Check: PASSED

All five modified source files and this SUMMARY exist on disk. All three commit hashes (`0b6e5bc`, `cc09481`, `aab64b7`) resolve in `git log`. Per-file test counts re-confirmed after the final commit: `test_model_catalog.py` 26 passed, `test_models_api.py` 4 passed.
