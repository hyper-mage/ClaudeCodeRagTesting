# Phase 4: Deploy Backend to Fly.io - Research

**Researched:** 2026-05-03
**Domain:** Fly.io Machines deploy of an existing FastAPI + Docling container, secrets via `flyctl secrets import`, SSE end-to-end smoke
**Confidence:** HIGH (Fly docs verified for fly.toml schema + auto_stop modes; MEDIUM on `flyctl secrets import` multi-line handling per known GitHub issue)

## Summary

Phase 4 is mostly mechanical — Phase 1 (CORS env), Phase 2 (Dockerfile, port 8000, appuser, smoke pattern), and Phase 3 (`.env.prod`, prod Supabase) already locked everything substantive. The four research bets are: (1) `fly.toml` v2 schema syntax for the exact key set in CONTEXT D-11; (2) ergonomics of `flyctl secrets import` from `.env.prod` on Windows PowerShell; (3) confirming Fly's edge proxy doesn't buffer `text/event-stream` so the SSE smoke test actually proves end-to-end streaming; (4) the exact JWT-helper extraction shape so `docker_smoke.sh` and `fly_smoke.sh` share one source of truth.

**Primary recommendation:** Use `[[http_service.checks]]` (array-of-tables, double brackets) for the health check; `auto_stop_machines = "suspend"` is a string per current Fly schema (string was once boolean — verify exact TOML quotes); pipe `.env.prod.backend` (a VITE_-stripped copy) into `flyctl secrets import` with a single bulk call to trigger one machine restart; don't add `X-Accel-Buffering: no` defensively in this phase — Fly's edge does not buffer `text/event-stream` by default and Phase 2's `sse-starlette` already sets the right headers (assert via the smoke script's chunk-count check).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**App identity + topology**
- **D-01:** Fly app name `boardgame-rag-prod`. Fallback `bgkb-rag-prod` if global name collides.
- **D-02:** Primary region `iad`. No multi-region.
- **D-03:** `fly.toml` at repo root (same dir as Dockerfile + `.dockerignore`).

**Secrets loading**
- **D-04:** Bulk-load via `flyctl secrets import < .env.prod` (single restart, atomic).
- **D-05:** `.env.prod` minimum keys: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`, `OPENROUTER_API_KEY`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT=boardgame-rag-prod`, `LANGSMITH_TRACING=true`, `TAVILY_API_KEY`, `CORS_ALLOWED_ORIGINS=http://localhost:5173`. VITE_* keys filtered out before import.
- **D-06:** Verify with `flyctl secrets list` + `docker run --rm <image> env | grep -E 'SUPABASE_SERVICE_ROLE_KEY|OPENROUTER_API_KEY'` returns empty.

**CORS placeholder strategy**
- **D-07:** `CORS_ALLOWED_ORIGINS=http://localhost:5173` for Phase 4 only.
- **D-08:** Phase 5 overwrites with real CF Pages URL.

**Docling model cache + volume**
- **D-09:** No Fly volume — models baked into image; `auto_stop_machines="suspend"` preserves process memory.
- **D-10:** Cold-start data collected by smoke; no auto-tuning. Volume deferred to v1.2+.

**fly.toml shape + keep-warm toggle**
- **D-11:** `app`, `primary_region="iad"`, `[build]` Dockerfile target, `[http_service]` (`internal_port=8000`, `force_https=true`, `auto_stop_machines="suspend"`, `auto_start_machines=true`, `min_machines_running=0`), health check on `/api/health` (`interval="30s"`, `timeout="5s"`, `method="GET"`), `[[vm]]` (`size="shared-cpu-1x"`, `memory="1gb"`).
- **D-12:** Keep-warm one-line commented toggle `# min_machines_running = 1  # …` directly above active `min_machines_running = 0`.

**Post-deploy smoke test**
- **D-13:** `backend/scripts/fly_smoke.sh $FLY_URL`: poll /api/health (60s timeout) → JWT login (helper from D-14) → POST /api/threads → POST /api/chat with Accept: text/event-stream, assert ≥3 SSE `data:` lines within 30s. No PDF upload.
- **D-14:** Extract Supabase JWT-login from `docker_smoke.sh` into `backend/scripts/_lib/get_test_jwt.sh` exposing `get_test_jwt`. Both scripts source it.

### Claude's Discretion

- Exact `fly.toml` formatting (key order, comment density, optional `[deploy]` section).
- VITE_* filter mechanism for `.env.prod` (temp file with `grep -v`, sed, or maintain separate `.env.prod.backend`).
- Polling cadence in `fly_smoke.sh` step 1 (2s/5s/exponential).
- `_lib/` location vs top-level `_get_test_jwt.sh`.
- `flyctl apps create` discrete task vs `flyctl launch --no-deploy --copy-config`.

### Deferred Ideas (OUT OF SCOPE)

- Fly volume for Docling cache (v1.2+).
- Multi-region / failover.
- CI-driven `fly deploy` (laptop-only this phase).
- `min_machines_running=1` enablement (commented toggle only).
- OBS-04 Supabase reachability check on `/api/health` (Phase 7).
- Rate limit / max-iter / spend cap (Phase 6).
- README + deploy badge (Phase 8).

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **DEPLOY-04** | `fly deploy` reaches public `*.fly.dev` URL serving `/api/health` and SSE chat end-to-end | Standard Stack §fly.toml, §flyctl deploy; Code Examples §fly_smoke.sh; Validation Architecture §runtime reachability + SSE chunk assertion |
| **DEPLOY-07** | `fly.toml` defaults to free-tier (`auto_stop_machines="suspend"`, no `min_machines_running` set) with documented one-line keep-warm toggle | Standard Stack §fly.toml; Validation Architecture §deployment artifacts (TOML key assertions) |
| **SEC-03** | All secrets in `flyctl secrets`; never committed; never baked into image | Standard Stack §flyctl secrets import; Validation Architecture §secrets state + image purity |

</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Raw OpenAI SDK only — no LangChain/LangGraph (already true in code; Phase 4 ships container as-is).
- Pydantic for structured LLM outputs (already in code).
- All tables under RLS; service-role key used only server-side (Phase 4 ships service role key as Fly secret — never to frontend).
- SSE for chat streaming (the exact thing Phase 4 smoke must prove still works through Fly's proxy).
- `venv` for backend dev (not relevant inside container).
- GSD workflow enforcement — Phase 4 surface (fly.toml, fly_smoke.sh, _lib/get_test_jwt.sh, docker_smoke.sh edit, .gitignore confirm) lands via `/gsd:execute-phase`.

## Standard Stack

### Core

| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| `flyctl` (a.k.a. `fly`) | latest stable (≥0.3, 2025+) | Fly.io CLI: app create, secrets import, deploy, logs | Only supported way to ship to Fly Machines from a hand-crafted Dockerfile + fly.toml |
| `fly.toml` | v2 schema | Declarative deploy config (build, vm, http_service, checks) | Required by `flyctl deploy`; resolved alongside Dockerfile from build context |
| Bash + curl + jq | system | Smoke test + JWT helper (matches Phase 2's `docker_smoke.sh`) | Already the convention in `backend/scripts/`; no new tool surface |
| `docker` (locally) | 26+ | Image grep verification (D-06) — `docker run --rm <image> env \| grep -E …` | Already required for Phase 2; reused for "no secret baked in" assertion |

No new Python or Node dependencies. Phase 2 image consumed unchanged.

### Supporting

| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| `flyctl logs -a $APP` | n/a | Debug deploy / cold-start failures | If `/api/health` doesn't go 200 within smoke's 60s budget |
| `flyctl secrets list -a $APP` | n/a | Verify D-06 — every key from D-05 is present | Smoke step 0 / verification |
| `flyctl status -a $APP` | n/a | Confirm machine count + state (started/suspended) | Post-deploy sanity |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `flyctl secrets import < .env.prod` (D-04) | `flyctl secrets set K=V K2=V2 ...` (single command) | Both bulk-restart once. `import` is shorter and reuses the `.env.prod` file directly; `set K=V ...` requires escaping in PowerShell for keys with `=` or quotes. Stick with import. |
| `flyctl launch --no-deploy --copy-config` | `flyctl apps create --name $APP` then `fly deploy` | `launch` may overwrite hand-crafted `fly.toml`. Discrete `apps create` keeps the committed fly.toml authoritative. |
| Bash smoke script | Python smoke script | Bash matches Phase 2 convention; Python adds runtime + `requests` dep. Keep bash. |

**Installation (no new deps to install — flyctl assumed present from CONTEXT):**

```bash
# verify locally before plan kickoff
flyctl version    # any 0.3.x or newer
flyctl auth whoami
```

**Version verification:** `flyctl` self-updates; pin via `flyctl version` capture in the smoke output, not via package manager.

## Architecture Patterns

### Recommended File Layout (delta from current repo)

```
<repo root>/
├── fly.toml                                    # CREATE (D-11/D-12)
├── Dockerfile                                  # exists (Phase 2)
├── .dockerignore                               # exists (Phase 1)
├── .env.prod                                   # exists (Phase 3, gitignored)
├── .gitignore                                  # MODIFY only if .env.prod not covered
└── backend/
    └── scripts/
        ├── docker_smoke.sh                     # MODIFY (consume helper, no behavior change)
        ├── fly_smoke.sh                        # CREATE (D-13)
        └── _lib/
            └── get_test_jwt.sh                 # CREATE (D-14)
```

### Pattern 1: Idempotent App Bootstrap

**What:** Separate "create app" from "deploy" so re-runs of the plan don't double-create.
**When to use:** Always — Fly app names are globally unique; `flyctl apps create --name X` errors hard if X exists, while `fly deploy` is happy to redeploy an existing app.

```bash
# Source: https://fly.io/docs/launch/deploy/
if ! flyctl apps list --json | jq -e --arg n "$APP" '.[] | select(.Name==$n)' >/dev/null; then
  flyctl apps create --name "$APP" --org personal
fi
flyctl secrets import -a "$APP" --stage < .env.prod.backend  # --stage = no deploy yet
flyctl deploy -a "$APP" --remote-only                         # single deploy with secrets present
```

The `--stage` flag is the key: it sets secrets without triggering a deploy/restart; the deploy that follows then has the secrets visible from machine start, eliminating the "deploy boots, machine restarts on secrets, deploy boots again" race.

### Pattern 2: Stable `[[http_service.checks]]` Health Check

**What:** Use the array-of-tables form (`[[ ]]`) for at least one check; this is the current canonical form per Fly docs.

```toml
# Source: https://fly.io/docs/reference/configuration/
[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = "suspend"   # string, NOT boolean (post-2024 schema)
  auto_start_machines = true
  min_machines_running = 0
  # min_machines_running = 1  # uncomment to keep machine warm (kills suspend/cold-start at the cost of always-on hours)

  [[http_service.checks]]
    grace_period = "10s"
    interval     = "30s"
    method       = "GET"
    timeout      = "5s"
    path         = "/api/health"
```

Single bracket `[http_service.checks]` is also accepted by current Fly TOML parser as a single check, but the canonical form in Fly's reference docs uses `[[ ]]`. **Use double brackets** to future-proof against ever adding a second check.

### Pattern 3: VITE_-stripped `.env.prod` for Backend Secrets

**What:** Backend Fly secrets must NOT contain `VITE_*` keys (those belong on Cloudflare Pages, Phase 5). `.env.prod` from Phase 3 D-11 contains both backend (`SUPABASE_URL`) and frontend (`VITE_SUPABASE_URL`) copies. Filter before import.

```bash
# Source: D-05; canonical pattern
# Option A (recommended): generate a temp filtered file, import it, delete it
grep -v -E '^VITE_' .env.prod > .env.prod.backend
flyctl secrets import -a "$APP" --stage < .env.prod.backend
rm .env.prod.backend

# Option B: pipe directly (no temp file)
grep -v -E '^VITE_' .env.prod | flyctl secrets import -a "$APP" --stage
```

Option B is shorter; Option A is observable (you can `cat .env.prod.backend` to eyeball the keys before import). Plan should pick one explicitly so executor doesn't have to choose.

**Windows PowerShell note:** `<` redirection works with PowerShell 7+ via `cmd /c "flyctl secrets import < file"` OR use `Get-Content file | flyctl secrets import`. Bash on Git-Bash / WSL is cleaner. The smoke script and plan tasks are bash, so this only affects developer-laptop ergonomics during the manual `flyctl secrets import` step — document the PowerShell variant in the plan.

### Pattern 4: Sourced JWT Helper (DRY)

**What:** Extract Supabase password-grant logic out of `docker_smoke.sh` into a sourceable function (D-14).

```bash
# backend/scripts/_lib/get_test_jwt.sh
# Usage: source this; call get_test_jwt; echo "$JWT"
get_test_jwt() {
  local AUTH_JSON
  AUTH_JSON=$(curl -sS -X POST "${VITE_SUPABASE_URL}/auth/v1/token?grant_type=password" \
    -H "apikey: ${VITE_SUPABASE_ANON_KEY}" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${TEST_EMAIL:-ragtest1@gmail.com}\",\"password\":\"${TEST_PASSWORD:-testpass123}\"}")
  JWT=$(echo "$AUTH_JSON" | jq -r '.access_token // empty')
  [ -n "$JWT" ] || { echo "[get_test_jwt] auth failed: $AUTH_JSON" >&2; return 1; }
  export JWT
}
```

Both `docker_smoke.sh` (uses dev `.env`) and `fly_smoke.sh` (uses `.env.prod`) source this. The function reads URL + anon key from already-loaded env, so the caller controls which env file is sourced. Phase 4 modifies `docker_smoke.sh` lines 86-94 (the inline auth block) to a single `get_test_jwt` call.

### Anti-Patterns to Avoid

- **Don't** add `X-Accel-Buffering: no` to `chat.py` defensively in this phase — there is no nginx in the path on Fly. Phase 2's `sse-starlette` already emits correct headers; Fly's edge proxy streams `text/event-stream` without buffering. Adding the header is a Phase 6/7 hardening item only if smoke fails.
- **Don't** set `auto_stop_machines = true` (legacy boolean) — current schema is the string `"suspend"` (or `"stop"` / `"off"`).
- **Don't** use `flyctl launch` interactively — it will offer to overwrite the hand-crafted `fly.toml` and prompt for VM size, leading to non-deterministic plan execution. Use `flyctl apps create` + `fly deploy`.
- **Don't** bake `.env.prod` into the image — Phase 1 D-09 already excludes `.env*` via `.dockerignore`. The D-06 image-grep verification is the regression test for this.
- **Don't** ship `min_machines_running = 1` — ROADMAP success criterion #1 prohibits it; the value `0` plus a commented `1` toggle satisfies the criterion.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Bulk loading env vars to Fly | A loop of `flyctl secrets set K=V` | `flyctl secrets import` (single bulk) | One restart vs N restarts; preserves quoting cleanly for typical key=value lines |
| Filtering `.env.prod` for backend-only keys | Custom python script | `grep -v -E '^VITE_'` | One-line shell idiom; matches Phase 2 conventions |
| Polling `/api/health` until 200 | Custom retry library | `curl -sSf` + bash for-loop with sleep (mirrors `docker_smoke.sh` pattern) | Already proven in Phase 2; ports 1:1 |
| SSE chunk reading from curl | Custom buffer-flushing wrapper | `curl -N --no-buffer` + line-by-line `read` loop | curl `-N` disables output buffering; portable |
| Supabase JWT password grant | Re-implement OAuth | Direct POST to `$SUPABASE_URL/auth/v1/token?grant_type=password` (already done in `docker_smoke.sh`) | Existing pattern; D-14 just extracts it |
| Verifying app exists before create | Try-catch on `apps create` exit codes | `flyctl apps list --json` + `jq` filter | Idempotent, observable |

**Key insight:** Every problem in this phase has a one-liner with a tool already on the developer laptop. The phase value is gluing them together correctly, not building infrastructure.

## Common Pitfalls

### Pitfall 1: `auto_stop_machines` schema confusion

**What goes wrong:** Pre-2024 docs/blog posts show `auto_stop_machines = true`. Current schema requires the string form (`"off"` / `"stop"` / `"suspend"`). Boolean form may silently coerce to `"stop"` (not the wanted `"suspend"`), losing the in-memory state-preservation property D-09 relies on.
**Why it happens:** Schema migrated; old examples still rank in search.
**How to avoid:** Verify the literal string `auto_stop_machines = "suspend"` (with quotes) by reading the committed `fly.toml` after generation; have the smoke or plan check `grep -F 'auto_stop_machines = "suspend"' fly.toml`.
**Warning signs:** `fly deploy` warning about deprecated boolean syntax; cold-start latency >> what suspend should give (suspend is "milliseconds", stop is "few seconds").

### Pitfall 2: `flyctl secrets import` quoting / multi-line

**What goes wrong:** Values containing `=`, multi-line PEMs, or surrounding double-quotes get mangled (per [GitHub issue #589](https://github.com/superfly/flyctl/issues/589)). LangSmith / Tavily / OpenRouter keys are simple alphanumeric — safe. SUPABASE_SERVICE_ROLE_KEY is a single-line JWT — safe. CORS_ALLOWED_ORIGINS may contain `,` and `/` — safe (no `=` or quotes). `.env.prod` for Phase 4 should NOT contain any multi-line values.
**Why it happens:** `flyctl secrets import` parses simple `KEY=VALUE\n` pairs and treats `"` as literal characters.
**How to avoid:** Plan must include a "scan `.env.prod` for unsupported lines" preflight step: `awk -F= 'NF<2 || /\\\\/{print NR": "$0}' .env.prod` should print zero lines. After import, `flyctl secrets list` must show all expected keys with sane created-at timestamps.
**Warning signs:** `LANGSMITH_PROJECT=boardgame-rag-prod` arriving in container as `"boardgame-rag-prod"` (with literal quotes) → boot-time observability mis-targets; CORS allowlist becoming `"http://localhost:5173"` → header mismatch.

### Pitfall 3: SSE buffering false alarm

**What goes wrong:** ROADMAP success criterion #4 demands "streams tokens without buffering." Smoke's chunk-count assertion can pass even if the chunks arrive in two large bursts (e.g. 2 `data:` lines at t=8s, 2 more at t=16s). That looks like buffering even though it isn't.
**Why it happens:** LLM token cadence varies; OpenRouter routing may chunk tokens at the upstream, not at Fly's proxy.
**How to avoid:** Smoke asserts ≥3 SSE `data:` lines arrive within 30s — that's necessary but not sufficient. Add a stronger test: assert first `data:` line arrives within `T_FIRST_CHUNK_MAX=20s` of POST (proves no end-of-stream buffering). Use `curl -N` (disables output buffering) + line-buffered `read` to capture timestamps.
**Warning signs:** `curl -N` against the Fly URL completes in one second with all chunks at the end (Fly proxy buffering, requires X-Accel-Buffering header) vs streams over 5-15 seconds with chunks interleaving (correct).

### Pitfall 4: First-deploy machine startup race

**What goes wrong:** `fly deploy` (without `--stage` on prior secrets) may start a machine before secrets land, machine boots, FastAPI errors on missing env, machine marked unhealthy, deploy retries, eventually succeeds — wasting 60-120s and producing alarming logs.
**Why it happens:** Default `flyctl secrets import` triggers a deploy itself; if you then `fly deploy`, you have two overlapping deploys.
**How to avoid:** Use `flyctl secrets import --stage` (explicitly stages the secret without deploying), then `fly deploy` once — the deploy applies the staged secrets atomically with the new image.
**Warning signs:** Deploy logs show two "machine update" events; `flyctl logs` shows "MissingSettings: SUPABASE_URL" before steady state.

### Pitfall 5: Prod test user doesn't exist (smoke auth fails)

**What goes wrong:** `fly_smoke.sh` calls Supabase password-grant for `ragtest1@gmail.com` against the prod project, but Phase 3 only seeded the system user (UUID `00000000-…`); `auth.users` was empty per Phase 3 UAT log. A test user was created via Supabase dashboard during UAT but is undocumented in 1Password.
**Why it happens:** Default KB seed (Phase 3 D-10) inserts as the system user, not a real auth user. Real auth user is needed for JWT login.
**How to avoid:** Plan task 0: verify `ragtest1@gmail.com` exists in prod auth.users via `psql -c "SELECT email FROM auth.users WHERE email='ragtest1@gmail.com'"` against prod DB OR via Supabase dashboard. If missing, plan creates it via `supabase.auth.admin.create_user()` (small Python one-liner using prod service-role key) and adds creds to the 1Password entry from Phase 3 D-18 as new fields `TEST_USER_EMAIL` / `TEST_USER_PASSWORD`. Specifics §line 153 of CONTEXT.md flags this exact verify-or-create branch.
**Warning signs:** Smoke step 2 fails with `{"error":"invalid_grant","error_description":"Invalid login credentials"}` from Supabase auth endpoint.

### Pitfall 6: Fly app name collision

**What goes wrong:** `flyctl apps create --name boardgame-rag-prod` returns `Error: app name boardgame-rag-prod is taken` because Fly app names are globally unique across all customers.
**Why it happens:** Common dictionary words; portfolio-friendly names get squatted.
**How to avoid:** Plan branches on the create result. Primary D-01: `boardgame-rag-prod`. Fallback (also D-01): `bgkb-rag-prod`. If both taken, escalate (rare but possible). Update `fly.toml` `app =` line and `fly_smoke.sh` default URL accordingly.
**Warning signs:** Create fails on first attempt; URL `https://boardgame-rag-prod.fly.dev` resolves to someone else's app.

### Pitfall 7: Image grep verification gives false-positive

**What goes wrong:** `docker run --rm <image> env | grep SUPABASE_SERVICE_ROLE_KEY` returns the key name (defined as a future env var, not value). Grep author wanted to prove no value leak; pattern matches the literal key name in some shell output.
**Why it happens:** `env` only prints currently set env vars. Inside the image with no `--env-file`, none of the secrets are set, so `env` is empty for them — but a developer might run with `.env` accidentally to "test prod build" and get false positive.
**How to avoid:** Verify with two checks: (1) `docker run --rm <image> env | grep -E 'SUPABASE_SERVICE_ROLE_KEY|OPENROUTER_API_KEY'` should be empty (no env file passed). (2) Layer/history check: `docker history --no-trunc <image> | grep -iE 'service_role|sk-or-v1|sk-[a-zA-Z0-9]'` should be empty (Phase 1's `.dockerignore` already prevents this; this is the belt-and-suspenders).
**Warning signs:** `docker history` shows COPY of `.env.prod`; image size jumps after a recent commit that touched `.dockerignore`.

## Runtime State Inventory

> Phase 4 is mostly greenfield (creates a new Fly app, new fly.toml, new smoke script). The "rename/migration" lens still applies because Phase 3 wrote `.env.prod` and 1Password entries that Phase 4 mutates. Items below.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — Phase 4 does not write to Supabase or any DB. Smoke script reads only. | None |
| Live service config | **Fly secrets (NEW):** Created by `flyctl secrets import` — lives on Fly servers, not in git. Source of truth = `.env.prod` + 1Password entry from Phase 3 D-18. **Fly app (NEW):** `boardgame-rag-prod` lives on Fly servers; identity is the global app name. | Code-edit only (no migration); document app name + URL in 1Password entry as new fields `FLY_APP_NAME` and `FLY_URL`. |
| OS-registered state | None — no Windows Task Scheduler, no pm2, no systemd. flyctl is installed locally on developer laptop; Fly Machines run on Fly infra. | None |
| Secrets/env vars | **`.env.prod`** at repo root (Phase 3 D-11) — gitignored, contains backend + VITE_* keys. **Phase 4 mutation:** add new key `CORS_ALLOWED_ORIGINS=http://localhost:5173` if not present; this is the placeholder per D-07. **1Password entry** `Supabase — boardgame-rag-prod` (Phase 3 D-18) — Phase 4 should add `FLY_APP_NAME`, `FLY_URL`, and (if Pitfall 5 triggers) `TEST_USER_EMAIL` / `TEST_USER_PASSWORD` fields. | Code edits only — `.env.prod` is already user-maintained; 1Password entry update is documentation. |
| Build artifacts | **Phase 2 image** (`boardgame-rag-backend:smoke` tag) — local Docker only, not pushed to a registry. Phase 4 deploys via `flyctl deploy` which builds remotely (or uses local docker depending on `--remote-only`). The smoke `:smoke` tag is independent. | None — Fly builds its own image from the same `Dockerfile`. |

**Canonical question:** *After fly_smoke.sh passes, what runtime systems carry phase-specific state?* → Fly app + Fly secrets only. Both are observable via `flyctl apps list` and `flyctl secrets list`. Both are reversible via `flyctl apps destroy` (planner should NOT include this; it's a manual rollback).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `flyctl` | All deploy + secrets ops | UNKNOWN at research time (probe failed in sandbox) | — | None — install per https://fly.io/docs/hands-on/install-flyctl/ as plan task 0. Hard blocker. |
| `docker` | Phase 2 smoke + image-grep verification (D-06) | Assumed YES (Phase 2 verified) | 26+ from Phase 2 | None |
| `bash` | All scripts | YES on Windows via Git Bash (Phase 2 confirmed) | n/a | — |
| `curl` | Smoke health poll + SSE assertion | YES (Phase 2 used it) | n/a | — |
| `jq` | JSON parsing in smoke | YES (Phase 2 used it; check in `docker_smoke.sh` line 43) | n/a | — |
| `grep`/`awk` | `.env.prod` filter + line-count assertions | YES (POSIX) | n/a | — |
| Supabase prod project | Smoke JWT login + chat backend | YES (Phase 3 complete; URL + keys in `.env.prod` + 1Password) | — | — |
| Phase 2 Dockerfile | Fly remote build | YES (Phase 2 complete) | — | — |
| Internet egress to fly.io | All ops | Assumed YES (developer laptop) | — | None |
| Fly.io account + payment method on file | `flyctl apps create` (Fly requires payment on file even for free-tier) | UNKNOWN | — | Plan task 0 verifies via `flyctl auth whoami` + checks org/payment via Fly dashboard if `apps create` errors on missing payment. |

**Missing dependencies with no fallback:**
- `flyctl` — must be installed before plan execution. Plan task 0 = "verify flyctl installed and authenticated, fail loudly if not."
- Fly.io account with payment on file — outside the plan's execution surface but a likely real-world blocker. Plan should mention but not gate (developer is sole executor).

**Missing dependencies with fallback:**
- None — every other dep is already proven by Phase 2/3.

## Code Examples

### `fly.toml` (verbatim, satisfies D-11/D-12 + ROADMAP §1)

```toml
# Source: D-11/D-12, https://fly.io/docs/reference/configuration/
app = "boardgame-rag-prod"
primary_region = "iad"

[build]
  dockerfile = "Dockerfile"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = "suspend"
  auto_start_machines = true
  # min_machines_running = 1  # uncomment to keep machine warm (kills suspend/cold-start at the cost of always-on hours)
  min_machines_running = 0

  [[http_service.checks]]
    grace_period = "10s"
    interval     = "30s"
    method       = "GET"
    timeout      = "5s"
    path         = "/api/health"

[[vm]]
  size   = "shared-cpu-1x"
  memory = "1gb"
```

### Bulk-secret-load command (D-04/D-05, satisfies SEC-03 + ROADMAP §2)

```bash
# Source: D-05; https://fly.io/docs/flyctl/secrets-import/
# (run from repo root, .env.prod present, gitignored)
APP="boardgame-rag-prod"

# 1. preflight: scan for unsupported lines (multi-line / blank-key)
awk -F= 'NF<2 || /\\\\$/ {print NR": "$0}' .env.prod   # expect zero output

# 2. filter VITE_* (frontend-only keys)
grep -v -E '^VITE_' .env.prod > .env.prod.backend
trap 'rm -f .env.prod.backend' EXIT

# 3. stage secrets without triggering a separate deploy
flyctl secrets import --stage -a "$APP" < .env.prod.backend

# 4. verify
flyctl secrets list -a "$APP"   # expect: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
                                #         SUPABASE_ANON_KEY, OPENROUTER_API_KEY,
                                #         LANGSMITH_API_KEY, LANGSMITH_PROJECT,
                                #         LANGSMITH_TRACING, TAVILY_API_KEY,
                                #         CORS_ALLOWED_ORIGINS
```

### Image-purity verification (D-06, satisfies SEC-03 image-grep)

```bash
# Source: D-06
IMG="boardgame-rag-backend:smoke"   # the tag built by docker_smoke.sh

# Layer 1: env is empty (no .env baked in as ENV directives)
docker run --rm "$IMG" env | grep -E 'SUPABASE_SERVICE_ROLE_KEY|OPENROUTER_API_KEY|TAVILY_API_KEY' \
  && { echo "FAIL: secret value baked into image as ENV"; exit 1; } \
  || echo "OK: no secrets in image env"

# Layer 2: history doesn't contain literal key prefixes (belt-and-suspenders against COPY .env.prod)
docker history --no-trunc "$IMG" | grep -iE 'service_role|sk-or-v1|sk-[A-Za-z0-9]{20,}|tvly-' \
  && { echo "FAIL: secret-shaped string in image layers"; exit 1; } \
  || echo "OK: no secret-shaped strings in image layers"
```

### `fly_smoke.sh` skeleton (D-13)

```bash
#!/usr/bin/env bash
# backend/scripts/fly_smoke.sh
# Phase 4 post-deploy smoke. Locked by 04-CONTEXT.md D-13/D-14.
# Usage: fly_smoke.sh https://boardgame-rag-prod.fly.dev
set -euo pipefail

FLY_URL="${1:?usage: fly_smoke.sh <FLY_URL>}"
HEALTH_TIMEOUT=60
SSE_TIMEOUT=30
MIN_DATA_LINES=3
FIRST_CHUNK_MAX=20   # seconds; Pitfall 3 hardening

# load prod env (Supabase URL + anon key for JWT)
[ -f .env.prod ] || { echo "FAIL: .env.prod missing"; exit 1; }
set -a; source .env.prod; set +a

# shared JWT helper (D-14)
# shellcheck source=_lib/get_test_jwt.sh
source "$(dirname "$0")/_lib/get_test_jwt.sh"

# 1. health poll (60s budget, 2s cadence — fast-fail loud)
echo "[smoke] polling $FLY_URL/api/health"
for i in $(seq 1 30); do
  if curl -sSf "$FLY_URL/api/health" >/dev/null 2>&1; then
    echo "[smoke] /api/health 200 after $((i*2))s"; break
  fi
  [ "$i" -eq 30 ] && { echo "FAIL: health never 200"; exit 1; }
  sleep 2
done

# 2. JWT
get_test_jwt   # exports $JWT

# 3. create thread
THREAD_ID=$(curl -sS -X POST "$FLY_URL/api/threads" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"title":"smoke"}' | jq -r '.id')
[ -n "$THREAD_ID" ] && [ "$THREAD_ID" != "null" ] || { echo "FAIL: thread create"; exit 1; }

# 4. SSE chat — assert ≥3 data: lines AND first chunk arrives < FIRST_CHUNK_MAX
START=$(date +%s)
DATA_LINES=0
FIRST_AT=0
# curl -N disables curl-side buffering; --max-time bounds total
curl -N --max-time "$SSE_TIMEOUT" \
  -H "Authorization: Bearer $JWT" \
  -H "Accept: text/event-stream" \
  -H "Content-Type: application/json" \
  -X POST "$FLY_URL/api/threads/$THREAD_ID/chat" \
  -d '{"message":"What is Catan?"}' | \
while IFS= read -r line; do
  [[ "$line" == data:* ]] || continue
  if [ "$DATA_LINES" -eq 0 ]; then FIRST_AT=$(( $(date +%s) - START )); fi
  DATA_LINES=$((DATA_LINES+1))
  [ "$DATA_LINES" -ge "$MIN_DATA_LINES" ] && break
done

[ "$DATA_LINES" -ge "$MIN_DATA_LINES" ] || { echo "FAIL: only $DATA_LINES SSE data lines"; exit 1; }
[ "$FIRST_AT" -le "$FIRST_CHUNK_MAX" ] || { echo "FAIL: first chunk took ${FIRST_AT}s (>$FIRST_CHUNK_MAX) — buffering"; exit 1; }
echo "[smoke] PASS: $DATA_LINES SSE lines, first chunk in ${FIRST_AT}s"
```

(Confirm the `/api/chat` route shape — `chat.py` line 30 shows `prefix="/api/threads"`, so the chat endpoint is `POST /api/threads/{thread_id}/chat` or similar. Plan task should grep `chat.py` for the actual SSE endpoint path before scripting.)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `auto_stop_machines = true` (boolean) | `auto_stop_machines = "suspend"` (string, one of off/stop/suspend) | Fly schema migrated 2024 | Boolean still parses but coerces to "stop"; loses fast-resume semantics |
| `flyctl launch` interactive bootstrap | `flyctl apps create` + committed `fly.toml` | 2023+ for IaC-style deploys | Deterministic plan execution |
| `fly secrets set` per key in a loop | `fly secrets import < .env` (bulk) | flyctl ≥0.1.x | One restart instead of N |
| Fly Apps v1 (Nomad) | Fly Machines v2 | 2023 | Not relevant — current docs are all v2; just don't follow pre-2023 guides |

**Deprecated/outdated:**
- `flyctl deploy` from a `procfile` without `fly.toml` — current path is `fly.toml` mandatory.
- Single-bracket `[http_service.checks]` (still works for one check; canonical is `[[ ]]`).

## Open Questions

1. **Does Fly's edge proxy buffer `text/event-stream` from a slim Python container in 2026?**
   - What we know: 2023-2024 community reports were resolved at the LiteFS proxy layer (not relevant here). Fly's main edge does not buffer `text/event-stream` by default.
   - What's unclear: No 2025-2026 explicit confirmation, but no regression reports surfaced in WebSearch either.
   - Recommendation: Trust default, verify in smoke (D-13 step 4 + Pitfall 3 first-chunk timing assertion). If smoke fails the buffering check, add `X-Accel-Buffering: no` header in `chat.py` as a Phase 4 hotfix task; otherwise leave alone.

2. **Does `auto_stop_machines = "suspend"` actually preserve the Docling singleton's loaded models in memory?**
   - What we know: Fly docs describe suspend as "faster than stop start" and CONTEXT D-09 assumes process state persists.
   - What's unclear: No explicit doc statement that Python heap survives suspend; community caveats exist.
   - Recommendation: D-10 already says smoke collects cold-start data without auto-tuning. After Phase 4 lands, observe first-chat latency post-suspend; if > 30s, the assumption broke and Phase 4.5 / v1.2+ revisits Fly volume. Don't gate Phase 4 on this.

3. **Does prod `auth.users` already contain `ragtest1@gmail.com`?**
   - What we know: Phase 3 03-UAT.md line 30 says "prod auth.users empty — created test user via Supabase dashboard" but doesn't say which email.
   - What's unclear: Whether the dashboard-created user is `ragtest1@gmail.com` or something else, and whether creds are the documented `testpass123`.
   - Recommendation: Plan task 0.5 explicitly verifies user exists with documented creds; if not, creates one via service-role admin API and updates 1Password.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | bash + curl + jq (matches Phase 2 convention; no pytest for ops scripts) |
| Config file | none — scripts are self-contained |
| Quick run command | `bash backend/scripts/fly_smoke.sh https://boardgame-rag-prod.fly.dev` |
| Full suite command | `bash backend/scripts/docker_smoke.sh && bash backend/scripts/fly_smoke.sh https://boardgame-rag-prod.fly.dev` |
| Phase gate | `fly_smoke.sh` exits 0 |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEPLOY-04 | `fly deploy` → public URL serves /api/health 200 | smoke (curl health poll) | `fly_smoke.sh` step 1 (`curl -sSf $FLY_URL/api/health`) | ❌ Wave 0 (script doesn't exist yet) |
| DEPLOY-04 | SSE chat streams end-to-end | smoke (chunk-count + first-chunk timing) | `fly_smoke.sh` step 4 (curl -N + line read + assertions) | ❌ Wave 0 |
| DEPLOY-07 | `fly.toml` shape per ROADMAP §1 | static (file inspection) | `bash -c 'grep -F "auto_stop_machines = \"suspend\"" fly.toml && grep -F "internal_port = 8000" fly.toml && grep -F "min_machines_running = 0" fly.toml && grep -F "memory = \"1gb\"" fly.toml && grep -F "size = \"shared-cpu-1x\"" fly.toml && grep -F "path = \"/api/health\"" fly.toml && grep -F "# min_machines_running = 1" fly.toml'` | ❌ Wave 0 (fly.toml doesn't exist) |
| DEPLOY-07 | Keep-warm toggle is one commented line above active value | static | `awk '/# min_machines_running = 1/{c=NR} /^min_machines_running = 0/{a=NR} END{exit !(a==c+1)}' fly.toml` | ❌ Wave 0 |
| SEC-03 | All secrets present in flyctl secrets list | runtime (flyctl) | `bash -c 'flyctl secrets list -a $APP --json \| jq -r ".[].Name" \| sort > /tmp/got; printf "%s\n" SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY SUPABASE_ANON_KEY OPENROUTER_API_KEY LANGSMITH_API_KEY LANGSMITH_PROJECT LANGSMITH_TRACING TAVILY_API_KEY CORS_ALLOWED_ORIGINS \| sort > /tmp/want; diff /tmp/want /tmp/got'` | ❌ Wave 0 (must be wired into smoke or plan as a verify task) |
| SEC-03 | No secret values baked into image | static (docker run + grep) | See Code Examples §Image-purity verification (two-layer check) | ❌ Wave 0 |
| SEC-03 | `.env.prod` not committed | static (git) | `bash -c 'git ls-files \| grep -E "^\.env\\.prod$" && exit 1 || exit 0'` + `git log --all --full-history -- .env.prod \| grep -q . && exit 1 || exit 0` | ✅ (`.gitignore` already covers `.env*` per Phase 1 D-09; this re-asserts) |

### Sampling Rate

- **Per task commit:** Static checks only — `grep`-against-`fly.toml` assertions, image-grep verification, secrets-list diff. No live deploy required for these to pass.
- **Per wave merge:** Full `bash backend/scripts/fly_smoke.sh $FLY_URL` after the deploy task completes.
- **Phase gate:** `fly_smoke.sh` exits 0 AND all static assertions pass AND `flyctl secrets list` matches D-05 set, before `/gsd:verify-work`.

### Wave 0 Gaps

- [ ] `fly.toml` — covers DEPLOY-07 (must be created with the exact key/value set)
- [ ] `backend/scripts/fly_smoke.sh` — covers DEPLOY-04 SSE end-to-end
- [ ] `backend/scripts/_lib/get_test_jwt.sh` — covers JWT acquisition shared between smoke scripts (D-14)
- [ ] `backend/scripts/docker_smoke.sh` modify — consume helper (no behavior change), keeps Phase 2 smoke green
- [ ] Image-purity assertions — can ride along inside `fly_smoke.sh` as a pre-deploy step OR a standalone `backend/scripts/verify_image_clean.sh` (planner picks)
- [ ] `flyctl secrets list` parity assertion — can ride inside `fly_smoke.sh` or be a separate `verify_secrets.sh`
- [ ] Plan-time static checks of `fly.toml` — can be part of plan-check or executor self-verify; no separate file needed if the plan task description includes the grep commands

## Sources

### Primary (HIGH confidence)
- https://fly.io/docs/reference/configuration/ — fly.toml schema, [build], [http_service], [[http_service.checks]], [[vm]] (verified 2026-05-03)
- https://fly.io/docs/launch/autostop-autostart/ — auto_stop_machines string values "off"/"stop"/"suspend", suspend is faster than stop (verified 2026-05-03)
- https://fly.io/docs/flyctl/secrets-import/ — `flyctl secrets import` reads stdin, `--stage` flag for deferred deploy (verified 2026-05-03)
- https://fly.io/docs/launch/deploy/ — `flyctl deploy` semantics (verified 2026-05-03)
- `.planning/phases/02-dockerize-backend/02-CONTEXT.md` — Phase 2 D-08/D-09 (port 8000, appuser, exec-form CMD, no $PORT)
- `.planning/phases/01-secrets-repo-hygiene/01-CONTEXT.md` — D-01/D-02 (CORS env-driven), D-09 (`.dockerignore` excludes `.env*`)
- `.planning/phases/03-prod-supabase-project/03-CONTEXT.md` — D-15 (region iad), D-11 (`.env.prod` location), D-18 (1Password entry shape)

### Secondary (MEDIUM confidence)
- https://github.com/superfly/flyctl/issues/589 — historical multi-line / quoted-value handling in `flyctl secrets import`. No 2025-2026 resolution found; assume single-line `KEY=VALUE` only.
- https://community.fly.io/t/response-buffering-inconsistent-results-when-reading-from-http-with-text-event-stream-mime-type/8430 — 2023 SSE buffering report tied to LiteFS proxy (not relevant to plain Fly Machines + sse-starlette path); no 2025-2026 regression report surfaced.
- `.planning/research/STACK.md` §"Fly.io" + Reference fly.toml — internal_port 8000, suspend, 1gb memory rationale.
- `.planning/research/PITFALLS.md` Pitfall 6 (cold start), Pitfall 8 (SSE proxy buffering) — both informed CONTEXT decisions; reused here.

### Tertiary (LOW confidence)
- https://fig.io/manual/flyctl/secrets/import — flyctl flag reference. Mirrors official docs; no contradiction.
- 2026 community blog references to `auto_stop_machines = "suspend"` semantics (in-memory state preservation) — Fly's own docs do not explicitly guarantee Python heap survives suspend; treat D-09 assumption as a working hypothesis to validate via smoke timing.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Fly schema verified against current docs; flyctl is canonical.
- Architecture: HIGH — patterns are 1:1 with Phase 2 conventions; no new abstractions.
- Pitfalls: HIGH for schema/secret/grep; MEDIUM for SSE buffering (relies on absence-of-evidence) and suspend-state preservation (community caveats unresolved).

**Research date:** 2026-05-03
**Valid until:** 2026-06-02 (30 days — Fly schema is stable; flyctl self-updates; recheck if `fly deploy` produces deprecation warnings).
