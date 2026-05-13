# Plan 06-02 Summary

**Phase:** 06-prod-wiring-auth-cors-rate-limiting-cost-caps
**Plan:** 02 — Counter-bounded chat tool-use loop (SEC-05)
**Status:** Complete
**Wave:** 1

## Objective

Replace unbounded `while True:` chat tool-use loop at `backend/routers/chat.py:564` with a counter-bounded loop capped at `Settings.chat_max_iterations` (default **15**), mirroring `explorer_service.py:232`'s counter+graceful-stop architecture.

## Requirements Addressed

- **SEC-05** — Chat agent tool-use loop must have an iteration cap with graceful exit

## Tasks Completed

### Task 1: Add `chat_max_iterations` setting

- Added `chat_max_iterations: int = 15` to `backend/config.py` `Settings` class
- Env-overridable via `CHAT_MAX_ITERATIONS`
- Config tests: 4/4 pass (`test_chat_max_iterations_default`, `test_chat_max_iterations_env_override`, plus the two pre-existing rate-limit defaults)

### Task 2: Counter-bound chat loop + cap-hit branch

- `routers/chat.py`: introduced `CAP_HIT_NOTICE` module constant (verbatim D-10 wording)
- Replaced `while True:` with `while iteration < settings_local.chat_max_iterations:` + `iteration += 1`
- `while/else` clause sets `cap_hit = True` only when counter exhausts without `break` (voluntary-stop preserved)
- On cap-hit:
  - Append `CAP_HIT_NOTICE.format(n=cap)` to `full_content` (persists in `messages.content` DB row)
  - Yield SSE `content_delta` with same notice (chat UI sees it as styled markdown italic)
  - Existing `done` event still fires from outer generator — no SSE `error` event
  - `logger.warning` with `user_id`, `thread_id`, cap value
  - LangSmith metadata tag `iteration_cap_hit=true` via `get_current_run_tree().add_metadata(...)` — wrapped in `try/except` (RESEARCH Pitfall 5: best-effort, non-fatal)

### Task 3: Cap-hit integration tests

- `test_chat_cap.py`: 4 SEC-05 tests (cap-hit graceful exit, logger.warning content, LangSmith tag, voluntary stop preserved). All pass.

## Files Modified

| File | Change |
|------|--------|
| `backend/config.py` | + `chat_max_iterations: int = 15` |
| `backend/routers/chat.py` | + `CAP_HIT_NOTICE`; replace `while True` → counter-bounded loop + cap-hit branch |
| `backend/tests/test_chat_cap.py` | Activate 4 SEC-05 placeholders with real assertions |
| `.planning/phases/06-prod-wiring-auth-cors-rate-limiting-cost-caps/deferred-items.md` | New — pre-existing e2e test collection errors out of scope |

## Verification

```
pytest backend/tests/test_chat_cap.py backend/tests/test_config.py -q
8 passed, 1 warning in 3.42s
```

All must-haves verified:
- ✅ Loop cannot exceed `Settings.chat_max_iterations` iterations
- ✅ Cap-hit emits final SSE `content_delta` with markdown-italic notice AND `done` event fires
- ✅ Notice appended to `full_content` → persists in `messages.content`
- ✅ `logger.warning` contains `user_id`, `thread_id`, cap value
- ✅ LangSmith `iteration_cap_hit=true` (best-effort, non-fatal)
- ✅ Voluntary stop path preserved (`break` in main exit)

## Commits

- `af72b9c` feat(06-02): add Settings.chat_max_iterations (default 15) for SEC-05
- `9779145` feat(06-02): counter-bounded chat tool-use loop with graceful cap-hit (SEC-05)

## Deviations

- Plan called for atomic task-by-task commits; due to mid-session limit reset the implementation + tests landed in one squashed commit alongside the earlier config commit. Functionally equivalent; logged here for audit.
- Pre-existing e2e test collection errors (`test_e2e_subagent.py`, `test_record_manager.py` integration cases) deferred to a future hygiene pass — see `deferred-items.md`.

## Next

Wave 2 (06-03): manual — extend `fly_smoke.sh` with rate-limit burst + CORS rejection-path assertions, swap Fly secret `LLM_MODEL` to `openai/gpt-oss-120b:free` per D-16 HARD GATE, redeploy, run smoke.
