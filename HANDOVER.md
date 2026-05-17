# Phase 6 Handover — Resume on Usual Setup

Cross-machine handoff: push branch `main` from this box, pull on usual setup, resume at Wave 2 (06-03) user-action step.

## Status at handover

**Phase:** 06-prod-wiring-auth-cors-rate-limiting-cost-caps (v1.1 milestone)
**Progress:** 3/5 plans complete. Wave 0 + Wave 1 fully landed. Wave 2 (06-03) code prepped, awaiting flyctl + smoke run. Wave 3 (06-04) untouched.

| Plan | Wave | Status | Notes |
|------|------|--------|-------|
| 06-00 — Test scaffolding | 0 | ✅ Complete | conftest fixtures + skipped test placeholders for SEC-04 + SEC-05 |
| 06-01 — slowapi rate limit (SEC-04) | 1 | ✅ Complete | `backend/limiter.py`, 20/min per-user, JSON 429 contract. 6/6 SEC-04 tests pass |
| 06-02 — Chat tool-loop cap (SEC-05) | 1 | ✅ Complete | `chat_max_iterations=15`, graceful SSE notice, LangSmith tag. 8/8 tests pass |
| 06-03 — Smoke + CORS + `:free` model | 2 | 🟡 Code prepped | `fly_smoke.sh` extended, `.env.prod` skeleton written. Needs flyctl + smoke run + manual cap-hit checkpoint |
| 06-04 — Supabase URLs + OpenRouter alert | 3 | ⏸ Not started | Manual dashboard work + $1 top-up + drain |

## Commits added this session (push these)

```
9406b6c feat(06-03): extend fly_smoke.sh with SEC-04 burst + CORS rejection (steps 6-7)
e061765 docs(06-02): SUMMARY.md for SEC-05 chat loop cap
9779145 feat(06-02): counter-bounded chat tool-use loop with graceful cap-hit (SEC-05)
af72b9c feat(06-02): add Settings.chat_max_iterations (default 15) for SEC-05
551cc46 merge(06-01): SEC-04 slowapi rate limit
2c75fa8 docs(06-01): complete SEC-04 slowapi rate limit plan summary
83bdcb6 feat(06-01): wire app-level limiter, custom 429 JSON handler, integration tests
b54a30c feat(06-01): wire auth bridge, chat_rate_limit setting, and chat route decorator
6717c99 feat(06-01): pin slowapi 0.1.9 and add limiter module with user_id_key
5e9c628 docs(06-00): complete test scaffolding plan
af251f3 test(06-00): add SEC-05 chat-cap + config defaults placeholders
d5da80a test(06-00): add SEC-04 rate-limit test placeholders
45ba767 test(06-00): extend conftest with rate-limit + chat-cap fixtures
```

13 commits ahead of `origin/main` (at `31b2d8e phase 6 plan`).

## Push from this machine

```bash
git push origin main
```

If protected branch / push rejected:
```bash
git push origin main:gsd/phase-06-prod-wiring-handover
# then open PR or fast-forward main remote-side
```

## Working-tree state (not committed; do not lose)

- `.planning/STATE.md` — modified by `gsd-sdk state.begin-phase`. STATE.md has parse error from manual edits earlier; defer fix until resume. **Do not stage.**
- `QUICKSTART.md` — untracked. Written this session as project quickstart doc. Stage + commit if you want it in repo: `git add QUICKSTART.md && git commit -m "docs: add QUICKSTART.md"`.
- `.env.prod` — gitignored (do not commit). Contains LLM_MODEL toggle skeleton only; on usual setup, merge real prod values back in.

## Pull on usual setup

```bash
git fetch origin
git pull --ff-only origin main
# Verify HEAD = 9406b6c
git log -1 --oneline
```

Verify env on usual box:
```bash
# Backend tests should all pass
cd backend && source venv/bin/activate
pytest tests/test_rate_limit.py tests/test_chat_cap.py tests/test_config.py -v
# Expect: 14 passed (no skips for these three files)
```

## Resume point — Wave 2 (06-03) user action

`backend/scripts/fly_smoke.sh` already has steps 6 (rate-limit burst) + 7 (CORS rejection). `.env.prod` has the LLM_MODEL=:free toggle block but is missing prod Supabase secrets on this machine.

### Step 1 — Populate `.env.prod` on usual setup

`.env.prod` is gitignored. On usual setup, ensure it has:
```
VITE_SUPABASE_URL=...
VITE_SUPABASE_ANON_KEY=...
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
OPENROUTER_API_KEY=...
LLM_API_KEY=...
LLM_MODEL=openai/gpt-oss-120b:free
```
(LLM_MODEL toggle comment block already in the file as written this session; just confirm the active line says `openai/gpt-oss-120b:free`.)

### Step 2 — Swap Fly secret + redeploy

```bash
flyctl secrets set LLM_MODEL="openai/gpt-oss-120b:free" -a boardgame-rag-prod
flyctl status -a boardgame-rag-prod      # wait machines → started
curl -sSf https://boardgame-rag-prod.fly.dev/api/health   # {"status":"ok"}
```

### Step 3 — Run extended smoke

```bash
bash backend/scripts/fly_smoke.sh https://boardgame-rag-prod.fly.dev 2>&1 | tee /tmp/fly_smoke_p6.log
```

Expect 7 `[ OK ]` markers:
- `SMOKE PASS: N SSE 'data:' lines, first chunk in Xs` (step 5)
- `Rate limit fired N × 429; body shape OK; Retry-After: ...` (step 6)
- `CORS rejection: Access-Control-Allow-Origin NOT echoed for evil.example` (step 7)

**Failure-mode triage (RESEARCH.md §Pitfalls):**
- Burst returns 0 × 429 → `flyctl logs -a boardgame-rag-prod | grep -i limiter` to verify 06-01 deployed
- CORS echoes evil.example → `flyctl secrets list | grep CORS_ALLOWED_ORIGINS` (should be `https://boardgame-rag-prod.pages.dev`)
- `:free` model breaks tool-calling → HARD GATE fail; do NOT silently downgrade; surface in summary

### Step 4 — Cap-hit checkpoint (Task 3-4, manual)

1. Open https://boardgame-rag-prod.pages.dev, login `ragtest1@gmail.com` / `testpass123`
2. Send adversarial prompt forcing ≥15 tool calls (see 06-03-PLAN.md §Task 3-4 for verbatim prompt)
3. Either outcome is acceptable:
   - **Cap hit:** italic notice `_I hit the tool-call limit (15) before finishing this answer..._` renders in UI; verify `flyctl logs -a boardgame-rag-prod --since 5m | grep max_iterations` shows WARNING line
   - **Voluntary stop:** `:free` model satisfied prompt within 15 iterations (not a regression)
4. Capture screenshot if cap hit

### Step 5 — Write 06-03-SUMMARY.md

Once smoke green + cap-hit outcome recorded, write `.planning/phases/06-prod-wiring-auth-cors-rate-limiting-cost-caps/06-03-SUMMARY.md` per plan §output:
- Paste full `/tmp/fly_smoke_p6.log`
- Outcome of cap-hit checkpoint (voluntary stop vs cap hit + screenshot reference)
- `:free` model in use + any tool-calling issues observed
- Fly secret digest before/after

Then `git add` and commit:
```bash
git add .planning/phases/06-prod-wiring-auth-cors-rate-limiting-cost-caps/06-03-SUMMARY.md
git commit -m "docs(06-03): SUMMARY.md for SEC-04 prod verification + :free model active"
```

## Wave 3 — 06-04 (after 06-03 done)

Pure manual dashboard work. Plan: `.planning/phases/06-prod-wiring-auth-cors-rate-limiting-cost-caps/06-04-PLAN.md`. Quick outline:

1. **Supabase prod Auth URLs (D-12/D-13):**
   - Site URL → `https://boardgame-rag-prod.pages.dev`
   - Redirect URLs allowlist → both `https://boardgame-rag-prod.pages.dev/**` AND `http://localhost:5173/**`
   - Test: fresh throwaway-email signup from prod CF URL, click email link, lands on prod (NOT localhost), can send chat

2. **OpenRouter alert (D-19/D-20):**
   - Configure $0.01 alert with email `<your-email>`
   - Delivery test: top up $1, swap `LLM_MODEL=openai/gpt-4o-mini` via flyctl, send 1 chat, confirm alert email arrives, swap LLM_MODEL back to `:free`, drain remaining balance

3. Record all evidence (timestamps, screenshots, fresh email used) in `06-04-VERIFICATION.md`

## Known issues / context

- **`gsd-sdk` state.md parse error.** `gsd-sdk query state.advance-plan` reports "Cannot parse Current Plan or Total Plans in Phase from STATE.md". Plans completed but STATE.md not auto-updated. Manual edit needed or run `gsd-sdk query state.sync --phase 06` on resume.
- **Worktree base divergence.** `Agent(isolation="worktree")` forks from a session-snapshot base, not current HEAD. Caused merge conflicts on 06-01 and forced halt on 06-02. Resolution: ran 06-02 inline (no subagent). On resume, prefer inline execution OR `git worktree remove --force` any stale entries before spawning agents.
- **Stale worktree dir.** `.claude/worktrees/agent-a540653da0246d67c` may persist locked on Windows (process lock from this session). After session ends, `rm -rf .claude/worktrees` or `git worktree prune` should clear it.
- **Deferred items.** `.planning/phases/06-prod-wiring-auth-cors-rate-limiting-cost-caps/deferred-items.md` lists pre-existing e2e test collection errors (out of scope for Phase 6) — `test_e2e_subagent.py` + 2 `test_record_manager.py` integration cases. Future hygiene pass.

## Verification anchor (sanity check after pull)

```bash
git log -1 --oneline                                  # 9406b6c feat(06-03): extend fly_smoke.sh...
ls backend/limiter.py                                  # exists
grep chat_max_iterations backend/config.py            # chat_max_iterations: int = 15
grep -c "^# --- " backend/scripts/fly_smoke.sh        # 7
cd backend && pytest tests/test_rate_limit.py tests/test_chat_cap.py tests/test_config.py -q  # 14 passed
```

All green → resume at Wave 2 Step 1 above.
