---
phase: 13-preferences-per-thread-model
plan: 04
subsystem: chat-send-path
tags: [deprecation-fallback, model-cache, notice-row, history-filter, SC4, D-06]
requires:
  - "13-01: messages role 'notice' CHECK; threads.model column"
  - "13-02: live schema applied (model_cache, threads.model, notice role)"
  - "12: model_cache table (the live-model registry)"
provides:
  - "At-send deprecated-pin fallback: persisted role='notice' row + model override to default"
  - "LLM history filtered to role in (user, assistant) — notice rows never reach the model"
affects:
  - backend/routers/chat.py
tech-stack:
  added: []
  patterns:
    - "Caller-side model override (resolver stays pure 3-tier — RESEARCH Open Question 2)"
    - "Cache-set membership check (read all model_ids, test membership) — tolerant of mid-refresh cache"
    - "Defensive cache reads (try/except → log + skip, never crash the turn)"
key-files:
  created: []
  modified:
    - "backend/routers/chat.py (deprecation check + notice insert + model override + history filter)"
    - "backend/tests/test_deprecated_model_fallback.py (memoize per-table mocks so insert assertion captures the handler call)"
decisions:
  - "Membership check via select('model_id').execute() over the full cache set (not .eq().maybe_single()) — survives Assumption A2 empty-cache guard in one read and matches the RED scaffold's mock contract"
  - "Override is a local reassignment of `model` in event_generator; _resolve_key_and_model body byte-identical (Open Question 2)"
  - "Notice composed server-side from controlled strings, inserted as plain text (FE escapes on render) — no HTML (T-13-XSS)"
metrics:
  duration: "~8 min"
  completed: 2026-06-24
  tasks: 2
  files: 2
  commits: 1
---

# Phase 13 Plan 04: At-Send Deprecated-Model Fallback Summary

At send time, a thread pinned to a model absent from a non-empty Phase 12 `model_cache` now persists a `role='notice'` row with the LOCKED UI-SPEC copy, overrides the turn's model to the user/owner default so the turn runs on the fallback (no crash), and the history map filters to `role in (user, assistant)` so notice rows never reach the LLM.

## What Was Built

### Task 1 — Deprecation detection + notice insert + model override + history filter

Two distinct, non-conflated mechanisms in `backend/routers/chat.py` `event_generator`:

1. **PRIOR-turn history filter (line ~743):** the history-map comprehension now keeps only `m["role"] in ("user", "assistant")`, so any `notice` rows persisted on earlier turns / reloads never flow into the LLM context on this or any future turn (Pitfall 3 / T-13-NOTICE-HISTORY). This is the load-bearing change asserted by `test_notice_excluded_from_history`.

2. **CURRENT-turn deprecation check (after the no_key early-return, before the assistant-row insert):**
   - Reads `thread_model = thread.data.get("model")`. If truthy:
   - Reads the live cache as a set of `model_id`s via `db.table("model_cache").select("model_id").execute()`.
   - **Assumption A2 guard:** only treats absence as deprecation when `cached_ids` is non-empty — an empty/mid-refresh cache never flags a valid pin.
   - If `thread_model not in cached_ids`: computes `default_model = _safe_user_default_model(db, user_id) or settings.llm_model`, inserts a `role='notice'` messages row with the LOCKED copy `Model "<thread_model>" is no longer available — using <default_model> instead.`, then **overrides** `model = default_model` for this turn.
   - All cache reads are wrapped in `try/except` (T-13-CRASH): a read error logs (scrubbed) and skips the notice, never crashing the turn.
   - The current-turn notice lands AFTER `messages`/`current_messages` are built, so it is inherently absent from this turn's model context — persistence + FE render only.

`_resolve_key_and_model` body is unchanged (the override lives in the caller — RESEARCH Open Question 2).

### Task 2 — Wave-merge backend suite gate

Ran the full backend suite as the wave-merge no-regression gate. Result: **203 passed, 2 errors** — the 2 errors are the documented pre-existing `test_record_manager.py` `user_id`-fixture debt (out of scope, see deferred-items.md). The no_key fail-closed refusal, SSE secret-scrub, and usage-drain (Phase 11 invariants) remain green (`test_key_model_resolution.py` + `test_chat_retry.py`: 10/10). No regression found → no code change in this task.

## Verification

| Check | Command | Result |
|-------|---------|--------|
| Deprecation fallback GREEN | `pytest tests/test_deprecated_model_fallback.py -q` | 2 passed |
| Resolution + retry invariants | `pytest tests/test_key_model_resolution.py tests/test_chat_retry.py -q` | 10 passed |
| Full backend suite (wave-merge gate) | `pytest -q` | 203 passed, 2 errors (pre-existing record_manager debt) |
| `_resolve_key_and_model` unchanged | `git diff routers/chat.py` | body byte-identical (only a new comment references it) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] RED scaffold's notice-insert assertion could never capture the handler's insert**
- **Found during:** Task 1 (GREEN gate)
- **Issue:** `test_deprecated_model_fallback.py::_build_fake_db` set `db.table.side_effect = _table`, where `_table` constructed a **fresh** `MagicMock` on every `db.table(name)` call. The assertion `db.table("messages").insert.call_args_list` therefore re-invoked `_table("messages")`, getting a brand-new mock with an empty `call_args_list` — so `test_inserts_notice_and_falls_back` could never observe the handler's `db.table("messages").insert({...role:"notice"...})` regardless of a correct implementation. (`test_notice_excluded_from_history` passed because it asserts on the stream-capture, not on the messages mock.)
- **Fix:** Memoized per-table mocks in `_build_fake_db` (a `_tables` dict; `_table` returns the cached instance per name). The `_table` body, the two test bodies, and the contract are otherwise untouched — this only makes the existing assertion observe a stable mock, preserving the scaffold's intent.
- **Files modified:** `backend/tests/test_deprecated_model_fallback.py`
- **Commit:** a497a7a

**2. [Implementation choice] Membership-set cache read instead of `.eq().maybe_single()`**
- **Found during:** Task 1
- **Detail:** The plan's `<interfaces>` sketch suggested `model_cache.select("model_id").eq("model_id", thread_model).maybe_single()`. The RED scaffold's mock does NOT filter by `.eq()` (it returns `model_cache_rows[0]` for any `.eq().maybe_single()`), so that path would falsely report the deprecated pin as cached. Switched to reading the full cache set via `select("model_id").execute()` and testing membership — which both matches the scaffold's mock contract (line 64) and folds the Assumption A2 empty-cache guard into the same read. Plan `<action>` explicitly permitted a lightweight existence read; this is functionally equivalent and more robust.
- **Files modified:** `backend/routers/chat.py`
- **Commit:** a497a7a

## Known Stubs

None — the notice row is composed from live `thread.model` + the resolved `default_model`; no placeholder/empty-data flow introduced.

## Threat Flags

None — no new network endpoint, auth path, or trust boundary beyond the plan's `<threat_model>` (T-13-NOTICE-HISTORY, T-13-XSS, T-13-A2, T-13-CRASH all mitigated as planned).

## Deferred Issues

- `tests/test_record_manager.py::test_check_duplicate_integration` and `::test_find_previous_version_integration` ERROR on a missing `user_id` fixture — pre-existing fixture debt (predates v1.1; STATE.md Pending Todos + deferred-items.md). Out of scope; not introduced by this plan.

## Self-Check: PASSED

- backend/routers/chat.py: FOUND (deprecation check + notice insert + model override + history filter)
- backend/tests/test_deprecated_model_fallback.py: FOUND (memoized mock; 2 passed)
- Commit a497a7a: present in history
