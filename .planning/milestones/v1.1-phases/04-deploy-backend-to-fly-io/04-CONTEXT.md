# Phase 4: Deploy Backend to Fly.io - Context

**Gathered:** 2026-05-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Deploy the Phase 2 container to a public Fly.io URL talking to the Phase 3 prod Supabase project. Deliverables:

1. `fly.toml` at repo root configured for free-tier (`shared-cpu-1x@1gb`, `internal_port=8000`, `/api/health` health check, `auto_stop_machines="suspend"`, no `min_machines_running`, with a one-line commented keep-warm toggle).
2. All runtime secrets loaded into Fly via `flyctl secrets import < .env.prod`; verified with `flyctl secrets list`; verified absent from pushed image via `docker inspect` / image grep.
3. `fly deploy` succeeds; `curl https://<app>.fly.dev/api/health` returns 200.
4. End-to-end SSE chat works against the Fly URL (post-deploy smoke script).

**Out of scope (other phases):**
- Frontend deploy + real `CORS_ALLOWED_ORIGINS` value (Phase 5)
- Supabase Auth redirect URLs for prod frontend (Phase 6 / SEC-01)
- LangSmith prod project config beyond setting the secret value (Phase 7)
- Rate limiting, max-iter cap, OpenRouter spend cap (Phase 6)
- README + deploy badge (Phase 8)

</domain>

<decisions>
## Implementation Decisions

### App identity + topology
- **D-01:** Fly app name `boardgame-rag-prod` (matches Phase 3 Supabase project name + Phase 7 LangSmith project name for naming consistency across surfaces). Public URL becomes `https://boardgame-rag-prod.fly.dev`. If `flyctl apps create --name boardgame-rag-prod` collides with an existing global Fly app, planner falls back to `bgkb-rag-prod` (and updates D-04 + smoke-script defaults accordingly).
- **D-02:** Primary region `iad` (us-east-1). Mirrors Phase 3 Supabase region per Phase 3 D-15. No multi-region.
- **D-03:** `fly.toml` lives at repo root (same dir as Phase 2 `Dockerfile` + `.dockerignore`). `flyctl deploy` resolves both from the same build context. No `--config` / `--dockerfile` flags needed.

### Secrets loading
- **D-04:** Bulk-load all runtime secrets via `flyctl secrets import < .env.prod` from the developer laptop after `flyctl apps create`. Atomic, single-command, reuses the gitignored `.env.prod` file already produced in Phase 3 (per Phase 3 D-11). Triggers a single machine restart instead of one per key.
- **D-05:** `.env.prod` must contain at minimum: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`, `OPENROUTER_API_KEY`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT=boardgame-rag-prod`, `LANGSMITH_TRACING=true`, `TAVILY_API_KEY`, `CORS_ALLOWED_ORIGINS=http://localhost:5173` (placeholder per D-08). Any `VITE_*` keys present in `.env.prod` for Phase 5 use are filtered out before `flyctl secrets import` (they should not land in backend Fly secrets) — planner picks the filter approach (grep -v on a temp copy, or a `.env.prod.backend` subset file). The 1Password entry from Phase 3 D-18 is the canonical source if `.env.prod` is missing locally.
- **D-06:** Verification step in plan: `flyctl secrets list` shows every key from D-05; `docker run --rm <image> env | grep -E 'SUPABASE_SERVICE_ROLE_KEY|OPENROUTER_API_KEY'` returns empty (proving values aren't baked into the image). The image grep maps to ROADMAP success criterion #2's "grep of the pushed image showing none of these values baked in".

### CORS placeholder strategy
- **D-07:** `CORS_ALLOWED_ORIGINS` is set as a Fly secret to the explicit string `http://localhost:5173` for Phase 4 only. Reasons: backend boots cleanly with a non-empty allowlist; SSE end-to-end smoke can run from a local browser pointing at the Fly URL; explicit value is unambiguous in `flyctl secrets list`.
- **D-08:** Phase 5 will overwrite `CORS_ALLOWED_ORIGINS` with the real `https://<cf-pages-subdomain>` value once the frontend deploy lands. This phase does NOT pre-guess the pages.dev subdomain.

### Docling model cache + volume
- **D-09:** No Fly volume mount in this phase. Models are baked into the image (Phase 2 D-06) and `auto_stop_machines="suspend"` preserves process memory across stop/start so the warm Docling singleton survives. Volumes add `[mounts]` config + a `flyctl volumes create` step for zero gain on suspend semantics.
- **D-10:** Cold-start data is collected by the smoke script (D-13) but no auto-tuning. The "evaluate Docling volume after Phase 4 smoke test" item in REQUIREMENTS.md "Future Requirements" stays deferred to v1.2+ unless the smoke test surfaces real pain.

### `fly.toml` shape + keep-warm toggle
- **D-11:** `fly.toml` includes (verbatim values that map to ROADMAP success criterion #1):
  - `app = "boardgame-rag-prod"` (or D-01 fallback)
  - `primary_region = "iad"`
  - `[build]` block targets the repo-root `Dockerfile`
  - `[http_service]` with `internal_port = 8000`, `force_https = true`, `auto_stop_machines = "suspend"`, `auto_start_machines = true`, `min_machines_running = 0`
  - `[http_service.checks]` (or `[[http_service.checks]]`) hitting `path = "/api/health"`, `interval = "30s"`, `timeout = "5s"`, `method = "GET"`
  - `[[vm]]` block with `size = "shared-cpu-1x"`, `memory = "1gb"`
- **D-12:** Keep-warm toggle is a single commented line `# min_machines_running = 1  # uncomment to keep machine warm (kills suspend/cold-start at the cost of always-on hours)` placed under `[http_service]` directly above the active `min_machines_running = 0`. No README change in this phase (Phase 8 README pass owns surfacing this).

### Post-deploy smoke test
- **D-13:** Commit `backend/scripts/fly_smoke.sh` that takes a single arg `$FLY_URL` (e.g. `https://boardgame-rag-prod.fly.dev`). Steps:
  1. Poll `GET $FLY_URL/api/health` until 200 or 60s timeout.
  2. Source the JWT-fetch helper (D-14) using `.env.prod` Supabase creds + the `ragtest1@gmail.com` / `testpass123` test user from CLAUDE.md.
  3. Issue `POST $FLY_URL/api/threads` with the JWT, capture thread_id.
  4. Issue `POST $FLY_URL/api/chat` with `{thread_id, message: "What is Catan?"}` and `Accept: text/event-stream`. Read response chunked; assert ≥3 SSE `data:` lines stream within 30s (proves no buffering at Fly proxy + agent loop returning content). Default KB seeded in Phase 3 makes this query deterministic.
  5. Print pass/fail summary; exit non-zero on any failure.
  Script does NOT upload PDFs (avoids polluting prod Storage; ingestion path is exercised by `docker_smoke.sh` against local containers).
- **D-14:** Refactor the Supabase JWT-login logic out of `backend/scripts/docker_smoke.sh` into a shared sourceable helper (e.g. `backend/scripts/_lib/get_test_jwt.sh` exposing a `get_test_jwt` function). Both `docker_smoke.sh` and `fly_smoke.sh` source it. DRY; updates to Supabase auth flow land in one place. Existing `docker_smoke.sh` is updated to consume the helper as part of this phase's surface (kept small — function-extraction only, no behavior change).

### Claude's Discretion
- Exact `fly.toml` formatting (TOML key order, comment density, `[deploy]` section if needed). D-11 lists required keys; planner picks layout.
- Filter mechanism for stripping VITE_* keys from `.env.prod` before `flyctl secrets import` (D-05) — temp file with grep -v, sed in-place, or maintain a separate `.env.prod.backend` subset. Pick whichever is shortest and least error-prone.
- Polling cadence in `fly_smoke.sh` (D-13 step 1) — 2s / 5s / exponential — pick something that's fast to fail loudly but doesn't hammer the health endpoint.
- Whether `backend/scripts/_lib/` is the right shared-helper location (D-14) or just a top-level `_get_test_jwt.sh`. Pick whichever fits existing scripts/ layout.
- Whether to pre-create the Fly app via `flyctl apps create` in a discrete plan task vs roll it into a single `flyctl launch --no-deploy --copy-config` invocation. Either is fine; plan should make the chosen path explicit so executor doesn't double-create.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase contract
- `.planning/ROADMAP.md` §Phase 4 — 4 success criteria (fly.toml shape, secrets via flyctl, fly deploy + /api/health 200, end-to-end SSE)
- `.planning/REQUIREMENTS.md` — DEPLOY-04, DEPLOY-07, SEC-03 definitions

### Research
- `.planning/research/SUMMARY.md` — Fly.io rationale + cost shape + cold-start risks
- `.planning/research/STACK.md` §"Fly.io" + §"Integration Points" — base image, internal port 8000, secrets list, CORS env-driven via `ALLOWED_ORIGINS`/`CORS_ALLOWED_ORIGINS`
- `.planning/research/PITFALLS.md` — SSE buffering proxies, suspend/resume cold-start cost, image bloat
- `.planning/research/ARCHITECTURE.md` — backend/frontend integration map; CORS allowlist pattern

### Prior-phase context (carry forward, do not re-plan)
- `.planning/phases/01-secrets-repo-hygiene/01-CONTEXT.md` §CORS Allowlist (D-01/D-02) — `CORS_ALLOWED_ORIGINS` is comma-separated string env var consumed by `Settings.cors_origins_list`; dev fallback `["http://localhost:5173"]` when unset.
- `.planning/phases/01-secrets-repo-hygiene/01-CONTEXT.md` §`.dockerignore Scope` (D-09) — `.env*` already excluded; `.env.prod` will not enter the image.
- `.planning/phases/02-dockerize-backend/02-CONTEXT.md` §Build Strategy + Runtime User (D-01/D-08/D-09) — single-stage `python:3.11-slim-bookworm`, runs as `appuser` UID 1000, exec-form CMD on port 8000, no `$PORT` expansion. Fly's `internal_port=8000` maps directly.
- `.planning/phases/02-dockerize-backend/02-CONTEXT.md` §Docling Model Preload (D-06/D-07) — models baked at build time under `~/.cache/docling`; no `DOCLING_CACHE_DIR` override; this is why D-09 declines a Fly volume.
- `.planning/phases/02-dockerize-backend/02-CONTEXT.md` §Smoke Test (D-11/D-12) — `backend/scripts/docker_smoke.sh` exists; D-14 above extracts its JWT helper for reuse here.
- `.planning/phases/03-prod-supabase-project/03-CONTEXT.md` §Project metadata (D-15/D-16) — region `iad`, project name `boardgame-rag-prod`. Mirrored by D-01/D-02 above.
- `.planning/phases/03-prod-supabase-project/03-CONTEXT.md` §Seed execution (D-11) — `.env.prod` exists at repo root, gitignored; canonical secrets source for D-04.

### Source files this phase TOUCHES (small surface)
- `fly.toml` at repo root — CREATE (per D-11/D-12)
- `backend/scripts/fly_smoke.sh` — CREATE (per D-13)
- `backend/scripts/_lib/get_test_jwt.sh` (or chosen path per D-14) — CREATE
- `backend/scripts/docker_smoke.sh` — MODIFY (function extraction only, per D-14)
- `.gitignore` — verify `.env.prod` is excluded (Phase 3 D-11 says it should be); add line if not.

### Source files this phase REFERENCES (do not modify)
- `Dockerfile` at repo root — Phase 2 deliverable; targets `main:app` on `0.0.0.0:8000`
- `backend/main.py:13-19` (or current line) — `/api/health` endpoint + CORSMiddleware reads `settings.cors_origins_list`
- `backend/config.py` — `CORS_ALLOWED_ORIGINS` field + parser (Phase 1 D-01/D-02)
- `backend/routers/chat.py` — `/api/chat` SSE endpoint targeted by smoke script

### Upstream docs
- https://fly.io/docs/reference/configuration/ — `fly.toml` reference (build, http_service, [[vm]], checks)
- https://fly.io/docs/flyctl/secrets/ — `flyctl secrets import` syntax + restart semantics
- https://fly.io/docs/launch/deploy/ — `flyctl deploy` from a Dockerfile
- https://fly.io/docs/apps/autostart-stop/ — `auto_stop_machines="suspend"` semantics + cold-start behavior

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/scripts/docker_smoke.sh` (Phase 2) — full Supabase login → JWT → upload → assert flow; D-14 extracts the JWT helper into `_lib/` for reuse in `fly_smoke.sh`.
- `backend/scripts/seed_default_kb.py` (Phase 3) — produced the deterministic prod default KB (10 board games incl. Catan); makes the smoke-test query `"What is Catan?"` answerable without per-run setup.
- `Settings.cors_origins_list` in `backend/config.py` — already parses the comma-separated env var into `list[str]` (Phase 1 D-01); Phase 4 just sets the value via `flyctl secrets`, no code change.
- `backend/main.py` `/api/health` endpoint — already returns 200 from a stateless handler (Phase 2 confirmed at line 28 of `02-CONTEXT.md`); satisfies Fly health check + smoke-test step 1 with no edits this phase.
- `.dockerignore` (Phase 1) — already excludes `.env*`, so `.env.prod` cannot leak into the Fly-deployed image even if present in the build context.

### Established Patterns
- Phase 2 set the convention that ops scripts live under `backend/scripts/` and shell over python where the auth dance is short. `fly_smoke.sh` follows that.
- All env-driven config goes through `Settings` in `backend/config.py`; runtime never reads raw `os.environ`. `flyctl secrets` map 1:1 to `Settings` fields with no glue code.
- Naming string `boardgame-rag-prod` is the cross-surface identifier (Supabase project, LangSmith project, Fly app). Don't introduce a fourth name here.

### Integration Points
- Fly secrets → container env → pydantic-settings `Settings` → `get_supabase()` / `get_llm_client()` / LangSmith init / CORSMiddleware. Whole chain already wired; Phase 4 supplies values, doesn't change wiring.
- Phase 5 (CF Pages frontend) consumes the public `https://boardgame-rag-prod.fly.dev` URL produced here as `VITE_API_BASE_URL`; the frontend deploy then back-fills `CORS_ALLOWED_ORIGINS` with its own URL via `flyctl secrets set`.
- Phase 7 (observability) consumes the same Fly app: adds OBS-04 Supabase reachability check to `/api/health`, points UptimeRobot at the URL minted here.

### Gotchas surfaced during scout / discussion
- `flyctl secrets import` triggers a machine restart on apply. Bulk import (D-04) restarts ONCE; per-key set restarts N times. Only matters for ergonomics; functional outcome is identical.
- `CORS_ALLOWED_ORIGINS=http://localhost:5173` (D-07) means SSE chat from a browser hosted on Cloudflare Pages (Phase 5) WILL be rejected until the Phase 5 update. That's intentional — smoke test in Phase 4 uses curl + JWT, not a browser, so CORS doesn't apply to it. Document this clearly so Phase 5 doesn't get a surprise 403.
- Fly's edge proxy supports SSE without buffering by default IF the response uses `Content-Type: text/event-stream` and the upstream doesn't set conflicting `Content-Length`. `sse-starlette` already does the right headers; verify in smoke test (D-13 step 4 asserts streamed chunks, not buffered single-shot).
- Fly app names must be globally unique. `flyctl apps create --name boardgame-rag-prod` may already be taken — D-01 names `bgkb-rag-prod` as fallback so executor isn't blocked.

</code_context>

<specifics>
## Specific Ideas

- ROADMAP success criterion #1 verbatim values must appear in `fly.toml`: `shared-cpu-1x@1gb`, `internal_port=8000`, `/api/health` health check, `auto_stop_machines="suspend"`, no `min_machines_running` set (active value `0` is acceptable; the prohibited state is "set to a non-zero number"), one-line commented keep-warm toggle.
- ROADMAP success criterion #2 secrets list (verbatim env var names): `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `OPENROUTER_API_KEY`, `LANGSMITH_*` (covers `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `LANGSMITH_TRACING`), `TAVILY_API_KEY`, `CORS_ALLOWED_ORIGINS` (placeholder).
- Test user creds for `fly_smoke.sh` JWT login: `ragtest1@gmail.com` / `testpass123` (from CLAUDE.md). These already exist in dev Supabase; the prod project from Phase 3 needs the same user OR the smoke test needs a separate prod test user. **Planner must check Phase 3 SUMMARY.md to confirm whether the test user was seeded into prod**, and if not, include creating one (or documenting that the smoke must run against an interactively-created prod user) as a task. Acceptable outcomes:
  1. Prod has the same `ragtest1@gmail.com` test user → smoke uses it directly.
  2. Prod doesn't have it → plan task creates one via `supabase.auth.admin.create_user()` against prod, with creds documented in 1Password (Phase 3 D-18 entry, new fields).

</specifics>

<deferred>
## Deferred Ideas

- Fly volume for Docling model cache — research note + REQUIREMENTS.md Future flag both push this to v1.2+. Re-evaluate after smoke-test cold-start data lands.
- Multi-region deploy / failover — explicitly out of scope per REQUIREMENTS.md.
- CI-driven `fly deploy` (GitHub Actions) — Phase 4 deploys from laptop. CI integration is Phase 8 polish or later.
- `min_machines_running=1` keep-warm enablement — toggle is documented in fly.toml but stays off until cost/latency data justifies the spend.
- Adding OBS-04 Supabase reachability check to `/api/health` — explicitly Phase 7 (Observability).
- Rate limit / max-iter / OpenRouter spend cap — Phase 6.
- README + deploy-status badge — Phase 8.

</deferred>

---

*Phase: 04-deploy-backend-to-fly-io*
*Context gathered: 2026-05-04*
