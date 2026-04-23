# Pitfalls Research — v1.1 Portfolio Deployment

**Domain:** Deploying FastAPI+Docling+Supabase+Vite SPA to Fly.io + Vercel + Supabase prod
**Researched:** 2026-04-22
**Confidence:** HIGH (most pitfalls verified against current code in this repo; a few deployment-platform specifics are MEDIUM)

Scope: mistakes made when adding deployment to *this specific* codebase. Each pitfall is tied to observed code/config in the repo where relevant, and mapped to a v1.1 deployment phase.

Assumed v1.1 phase skeleton (used below for mapping — roadmap agent may rename):

- **P1 Secrets & Repo Hygiene** — secret audit, `.dockerignore`, `.gitignore`, env var plan
- **P2 Dockerize Backend** — Dockerfile with Docling native deps, local smoke test
- **P3 Supabase Prod Project** — migrations, extensions, storage policies, seed
- **P4 Fly.io Backend Deploy** — secrets, machines, scale, health checks
- **P5 Vercel Frontend Deploy** — env vars, API base URL, SPA rewrites
- **P6 CORS, Auth, Streaming Hardening** — origins, redirect URLs, SSE proxy behavior
- **P7 Observability & Rate Limiting** — LangSmith prod project, Sentry, rate limit, uptime
- **P8 Demo Hardening** — demo creds, README, final smoke test

## Critical Pitfalls

### Pitfall 1: VITE_* env vars leak secret keys into the frontend bundle

**What goes wrong:**
A developer adds `VITE_SUPABASE_SERVICE_ROLE_KEY=...` or `VITE_OPENAI_API_KEY=...` to Vercel env vars thinking it's "just for the frontend." Vite inlines any `VITE_*` variable into the production bundle, so the key ships in plaintext JS served to every visitor.

**Why it happens:**
- `backend/config.py` already mixes concerns: `vite_supabase_url` and `vite_supabase_anon_key` are declared on the backend `Settings` class. Someone copying that pattern adds `vite_supabase_service_role_key` "for parity" and wires it into the frontend build.
- `.env` at the repo root is loaded by both frontend (`envDir: '..'`) and backend, so there's no physical separation of which keys are safe to expose.
- Vercel's UI doesn't warn when a `VITE_*` variable name looks like a secret.

**How to avoid:**
- Only two `VITE_*` vars are ever allowed: `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, plus `VITE_API_BASE_URL` for the Fly backend. Document this explicitly in README and Vercel project.
- Add a pre-build guard: a tiny script in `frontend/scripts/check-env.cjs` that fails `npm run build` if any `VITE_*` var name matches `/SERVICE_ROLE|SECRET|PRIVATE|OPENAI|OPENROUTER|LANGSMITH|TAVILY|RERANK|JWT/i`.
- After deploy, grep the built assets for prefixes of known secret keys (`sk-`, `sb_secret_`, `eyJ...` longer than anon) before promoting.

**Warning signs:**
- `curl https://<vercel>/assets/index-*.js | grep -Ei 'service_role|sk-proj|sk-or-'` returns matches.
- Supabase dashboard shows writes/reads bypassing RLS from frontend IPs.
- Usage dashboards spike from anonymous traffic.

**Phase to address:** P1 (define allowed VITE_* vars), P5 (Vercel env setup + post-build grep), P8 (final audit)

---

### Pitfall 2: Service role key used from the frontend (RLS bypass)

**What goes wrong:**
To "fix" a 401/RLS error quickly, a dev swaps the frontend's Supabase client from anon key to service role, or proxies a service-role-authenticated call through a public API endpoint with no auth. All RLS — including the public/private KB split built in Phase 1 — is bypassed. Any visitor can read or modify every user's documents.

**Why it happens:**
- The backend uses the service role key by design (`supabase_service_role_key` in `Settings`), so the pattern is already in the codebase.
- `frontend/src/lib/supabase.ts` uses the anon key today, but nothing structurally prevents someone from creating a second client with a different key.
- The app's RLS model is "mixed-visibility" (see migration 020) — a single misuse reveals both private docs and lets anonymous users mutate the default KB.

**How to avoid:**
- Hard rule: service role key exists only in Fly secrets and in local `.env` (never in Vercel, never in frontend code).
- Add an ESLint rule or a grep guard in CI: fail if `frontend/` contains `service_role`, `SERVICE_ROLE`, or `createClient(.*SERVICE`.
- Every backend endpoint that uses the service-role client MUST also call `get_user_id()` dependency and filter by `user_id` in SQL — do not rely on RLS when using service role. Verify this is true for all existing routers before deploy (spot-check `threads.py`, `chat.py`, `documents.py`, `folders.py`).
- Write one RLS smoke test against prod: sign in as `ragtest1`, try to read another user's doc by ID, expect 404/403.

**Warning signs:**
- Any reference to `service_role` in a file under `frontend/`.
- Network tab shows requests to `*.supabase.co/rest/v1/...` from the browser with an `Authorization: Bearer` token that is not a short-lived JWT (service role is a long static JWT with `role: service_role` claim — decode at jwt.io).
- Any user can see another user's private documents in the UI.

**Phase to address:** P1 (CI guard), P6 (auth hardening + RLS smoke test), P8 (final audit)

---

### Pitfall 3: `.env` committed or leaked into Docker image

**What goes wrong:**
Either `.env` gets committed to git (history poisoned, rotation required), or — more subtly — it gets `COPY . .`'d into the Docker image even though it's gitignored. The image is public (Fly builders, registry) and now contains prod secrets.

**Why it happens:**
- No `.dockerignore` present in the repo today. `Dockerfile` with `COPY . /app` will pull in `.env`, `backend/venv/`, `frontend/node_modules/`, `.planning/`, `.agent/`, and `.git/`.
- `backend/config.py` does `load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))`, so the app functions fine when `.env` is baked into the image — masks the mistake.
- Developers sometimes re-run `git add -A` after `.gitignore` changes and accidentally stage files that had already been tracked.

**How to avoid:**
- Create `.dockerignore` in P1 with at minimum: `.env`, `.env.*`, `.git`, `.gitignore`, `backend/venv/`, `backend/__pycache__/`, `**/__pycache__/`, `frontend/node_modules/`, `frontend/dist/`, `.planning/`, `.agent/`, `.claude/`, `*.md`, `tests/`, `backend/tests/`.
- In the Dockerfile, prefer `COPY backend/requirements.txt .` then `COPY backend/ /app/` (explicit, not `COPY . .`).
- Remove `load_dotenv(...)` call when `ENV == "production"`, or guard it so it only runs if the file exists. Fly injects env vars directly; relying on `.env` in prod is a smell.
- Add a CI check that `git ls-files | grep -E '^\.env$'` returns nothing and that the repo's git history doesn't contain `.env` (`git log --all --full-history -- .env`).
- After building the image locally: `docker run --rm <image> sh -c 'ls -la /app /app/.. ; env | grep -i key'` to confirm no secret material is baked in.

**Warning signs:**
- `docker image inspect` shows layer sizes much larger than expected.
- `.env` appears in `git status` as tracked.
- Fly deploy works even when you "forget" to set secrets — that means the image has them.

**Phase to address:** P1 (dockerignore + git history audit), P2 (Dockerfile review + image inspection)

---

### Pitfall 4: Docker image bloat from Docling pushes past free-tier disk limits

**What goes wrong:**
Docling (unpinned in `requirements.txt`) pulls in `easyocr`, `torch`, `transformers`, model weights, and native libs. A naive `python:3.11` base image with `pip install -r requirements.txt` produces a 6–10+ GB image. Fly.io free-tier machines have limited rootfs (default ~8 GB), push times balloon to 20+ minutes, and cold-start pulls time out. Vercel is unaffected (frontend only).

**Why it happens:**
- `docling` in `requirements.txt` has no pin — `pip install docling` grabs the full easyocr+torch dependency set even if you only use PDF text extraction.
- `python:3.11` (not `-slim`) base ships with compilers and dev headers.
- `pip` caches wheels in `/root/.cache/pip` — not cleaned between layers.
- Docling also downloads ML models on first use; if they're cached into the image, that adds gigabytes.

**How to avoid:**
- Use multi-stage Docker build: stage 1 `python:3.11-slim` with `build-essential` to compile wheels, stage 2 `python:3.11-slim` copying only the site-packages.
- Clean aggressively: `pip install --no-cache-dir`, `apt-get clean && rm -rf /var/lib/apt/lists/*`.
- Pin `docling` to a known version and audit its extras. If only PDF/DOCX are needed, check whether `docling-core` + specific backends can replace full `docling` — current code uses `DocumentConverter` so likely needs full package, but verify.
- Pre-download Docling models during build into a known path, then set `HF_HOME`/`TORCH_HOME` to that path so prod cold starts don't hit the network. Keep models out of the image only if you can tolerate first-request latency.
- Target <2 GB image. Check with `docker images` after build.

**Warning signs:**
- `fly deploy` upload > 5 minutes.
- `Docker image size: X GB` in Fly logs with X > 4.
- Cold starts fail because image pull exceeds machine timeout.
- `pip install` logs show `torch-2.x-cu...whl (800 MB)` being downloaded.

**Phase to address:** P2 (Dockerfile multi-stage, size budget)

---

### Pitfall 5: Docling missing system libs in slim image (runtime failures, not build failures)

**What goes wrong:**
Build succeeds, container starts, `/api/health` returns 200 — but the first PDF upload fails with `OSError: cannot load libGL.so.1` or `libmagic not found` or `tesseract: command not found`. Error only surfaces when `DocumentConverter` is actually invoked, so CI and health checks pass.

**Why it happens:**
- `python:3.11-slim` omits system libraries. Docling (via easyocr/OpenCV/pdfium) needs `libgl1`, `libglib2.0-0`, `libsm6`, `libxext6`, `libxrender1`. If OCR on images (Phase 2 validated feature) is used, `tesseract-ocr` and `libtesseract-dev` are needed. `libmagic1` is needed if any code path does MIME sniffing.
- Existing `backend/services/parsing_service.py` uses a lazy `_get_converter()` singleton — the failure doesn't happen at import time, it happens on first conversion.

**How to avoid:**
- In the Dockerfile runtime stage, install: `apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libmagic1 poppler-utils tesseract-ocr tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*`.
- Add a post-deploy smoke test that uploads a real PDF, a real image (OCR path), and a real XLSX to the live backend before calling the deploy done.
- Consider `python:3.11-bookworm` (full Debian) instead of slim — costs ~100 MB but eliminates the "which system lib is missing" game. Tradeoff: bigger image.

**Warning signs:**
- `/api/health` is green but `POST /api/documents` returns 500 with `libGL.so.1` or `ImportError` in Fly logs.
- Docling works locally (on macOS/Windows with full system) but fails in container.
- Ingestion status in UI gets stuck at `processing` or flips to `failed` with a cryptic error.

**Phase to address:** P2 (Dockerfile system deps), P8 (real-file smoke test before demo)

---

### Pitfall 6: Fly free-tier cold starts kill SSE streams and Realtime reconnects

**What goes wrong:**
Fly free-tier apps can auto-stop machines when idle. First request after idle cold-starts the machine — taking 5–30+ seconds with this image size (Docling, torch). Symptoms: user clicks "Send" in chat, SSE connection times out before first token. Supabase Realtime channel for ingestion reconnects mid-upload and status never updates. Frontend shows a spinner forever.

**Why it happens:**
- `auto_stop_machines = true` is the Fly default for cost savings.
- Cold start has to load Docling's DocumentConverter and torch on first import if `parsing_service.py` is hit (current code is lazy, so chat-only cold start is faster — good).
- Frontend `apiFetch` likely doesn't have retry or user-visible "server waking up" UX.
- EventSource and `fetch`-based SSE both have ~30s idle timeouts on many proxies.

**How to avoid:**
- Set `min_machines_running = 1` in `fly.toml` for the portfolio demo — trades a few dollars/month for reliability. If truly free-tier is mandatory: keep `auto_stop_machines = true` but add `auto_start_machines = true` and pre-warm on page load.
- Add a lightweight `/api/health` ping from the frontend on app mount to trigger cold start before the user sends their first chat.
- In the chat UI, show a "Waking up server..." state if the first SSE token takes > 3s.
- For the Docling code path, pre-import in `main.py` at startup so the model load cost is paid once, during the health-check-passing window.
- Tune Fly `[[services.http_checks]]` grace period to > image pull + startup time.

**Warning signs:**
- First chat after idle returns a 502 or hangs.
- `fly logs` shows "Starting instance..." right when user reports the timeout.
- Ingestion UI stays on "Processing" after the page is refreshed.

**Phase to address:** P4 (Fly config + min_machines), P6 (frontend warmup ping)

---

### Pitfall 7: CORS misconfigured — `allow_origins=["*"]` + `allow_credentials=True` is invalid and will be silently rejected by browsers

**What goes wrong:**
Current `backend/main.py` has:
```python
allow_origins=["*"],
allow_credentials=True,
```
Browsers reject `Access-Control-Allow-Origin: *` combined with `Access-Control-Allow-Credentials: true` — the spec disallows it. Locally this might work because no auth cookies are sent, but in prod with Supabase auth or when the frontend tries to include credentials, the browser blocks the response and the user sees network errors with no useful console message.

**Why it happens:**
- "Set it to `*` for now" is a common dev shortcut that gets left in.
- Current auth model uses `Authorization: Bearer <jwt>` header (not cookies), so `allow_credentials` isn't actually required — but it's enabled anyway.
- The bug is latent: chat may work while the actual CORS failure hides behind `net::ERR_FAILED`.

**How to avoid:**
- Set `allow_origins` to an explicit list from an env var: `["https://<project>.vercel.app", "https://<custom-domain>"]` (and localhost for dev).
- Set `allow_credentials=False` unless cookies are actually in use (they aren't in this codebase).
- `allow_methods` and `allow_headers` can stay broad but prefer explicit: `["GET","POST","DELETE","OPTIONS"]`, `["Authorization","Content-Type","Accept"]`.
- Test CORS from the deployed Vercel origin before demo: open browser devtools, hit chat endpoint, confirm preflight OPTIONS returns `Access-Control-Allow-Origin: https://<vercel>` (not `*`).

**Warning signs:**
- Browser console: `Access-Control-Allow-Origin` header contains `*` and credentials mode is `include` — spec violation.
- Chat requests fail with `TypeError: Failed to fetch` from Vercel but work from `localhost`.
- Preflight OPTIONS returns 200 but the follow-up POST is blocked.

**Phase to address:** P6 (CORS tightening — explicit allowlist, drop credentials)

---

### Pitfall 8: SSE broken by proxy buffering (Fly edge, Cloudflare, Vercel rewrites)

**What goes wrong:**
Backend streams tokens via `sse-starlette`. Everything works locally. On Fly, the edge proxy buffers the response until a size or time threshold, so the user sees nothing for 5–20 seconds, then the entire response dumps at once. Or worse, if the frontend proxies `/api/*` through Vercel rewrites to the Fly backend, Vercel's edge buffers the SSE and streaming is effectively dead.

**Why it happens:**
- Default HTTP proxies buffer for performance.
- `sse-starlette` sends correct headers, but some proxies only disable buffering when they also see `X-Accel-Buffering: no` (nginx convention) or when the response has `Content-Type: text/event-stream` AND no `Content-Length`.
- Vercel's `vercel.json` rewrites to external origins don't reliably stream — the recommended pattern is to call Fly directly from the browser, not proxy through Vercel.

**How to avoid:**
- Set `VITE_API_BASE_URL=https://<fly-app>.fly.dev` in Vercel and call the backend directly from the browser (crosses origins — CORS from Pitfall 7 must be correct). Do NOT rewrite `/api/*` through Vercel for SSE endpoints.
- In the chat route, explicitly add headers: `X-Accel-Buffering: no`, `Cache-Control: no-cache, no-transform`, `Connection: keep-alive`. `sse-starlette.EventSourceResponse` already sets most but not `X-Accel-Buffering`.
- On Fly, confirm no additional reverse proxy with buffering sits in front. Fly-proxy should stream by default for `text/event-stream`.
- Smoke test with `curl -N https://<fly>.fly.dev/api/chat/... ` and watch for tokens arriving one-by-one, not in a burst at the end.

**Warning signs:**
- Local dev streams character-by-character; prod streams one big chunk after a long pause.
- `curl -N` shows identical behavior.
- `fetch` on frontend hits `ReadableStream` reader but `read()` resolves only once, with the full message.

**Phase to address:** P5 (direct frontend→Fly calls, no Vercel SSE rewrite), P6 (response headers + curl smoke test)

---

### Pitfall 9: Supabase Auth redirect URLs not updated — email verification dead in prod

**What goes wrong:**
User signs up on the Vercel URL, clicks the verification email, lands on `http://localhost:5173/#access_token=...` (the dev redirect), confirmation fails, account stays unverified, user blocked. Same issue breaks password reset flows.

**Why it happens:**
- Supabase sends auth emails using the redirect URL configured on the project. A fresh prod project defaults to `http://localhost:3000` or whatever was set during dev.
- The redirect is set per-Supabase-project, so the new prod project needs its own configuration — copying the dev one doesn't happen automatically.
- This is NOT a code change — it's a dashboard config that's easy to forget.

**How to avoid:**
- During P3 (Supabase prod setup), explicitly configure:
  - **Site URL:** `https://<project>.vercel.app`
  - **Additional Redirect URLs:** include both `https://<project>.vercel.app` and `https://<project>.vercel.app/login` and `http://localhost:5173` for local dev against prod.
- If using `emailRedirectTo` on the frontend signup call, make sure it points to a valid configured URL.
- Add to demo-hardening checklist: "Create brand new account from a clean browser, verify email, log in, upload a doc" — end-to-end dry run.

**Warning signs:**
- Verification email link redirects to localhost.
- User reports "clicked the link but still can't log in."
- Supabase dashboard → Auth → Users shows users with `email_confirmed_at = null` despite having clicked the link.

**Phase to address:** P3 (prod project config), P8 (E2E signup dry run)

---

### Pitfall 10: pgvector / ltree / pg_trgm extensions not enabled on the prod Supabase project

**What goes wrong:**
Migrations are applied in order, but one of them (`004_enable_pgvector.sql`, `016_enable_ltree.sql`) fails because the extension wasn't enabled at the project level, OR the migration silently succeeds but RPC functions that use operators fail at runtime with `operator does not exist: vector <=> vector`. The app deploys, chat works for non-RAG messages, but every `search_documents` call 500s.

**Why it happens:**
- Supabase projects have a default set of enabled extensions, but `vector`, `ltree`, and sometimes `pg_trgm` (used for fuzzy search in keyword_search) require explicit enabling via Dashboard → Database → Extensions or `create extension if not exists`.
- `004_enable_pgvector.sql` does `create extension`, but it needs the right ROLE — running via Supabase Studio works, running via external migration tool may not.
- Some extensions create types in specific schemas (`extensions.vector`); if RLS policies or RPCs reference an unqualified type, they fail.

**How to avoid:**
- In P3, run migrations in order 001 → 024 via `supabase db push` connected to the prod project. Do not copy SQL into Studio ad-hoc — use the migration runner.
- After migrations, run a verification query: `SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector','ltree','pg_trgm')`. All three must be present.
- Run end-to-end search smoke test: seed one default KB document, call `POST /api/chat/...` with a query that forces `search_documents`, confirm results return (not a 500).
- Check each RPC exists: `match_document_chunks`, `keyword_search_chunks`, `execute_readonly_query`, `kb_grep_regex`, `kb_glob`. A `SELECT proname FROM pg_proc WHERE proname LIKE 'kb_%' OR proname LIKE '%search%'` confirms them.

**Warning signs:**
- Chat works but "search your documents" queries return no results or 500.
- `fly logs` shows `operator does not exist: public.vector <=> public.vector`.
- Ingestion succeeds but vector column in `document_chunks` is all nulls or errors.

**Phase to address:** P3 (migrations + extension verification), P8 (search smoke test)

---

### Pitfall 11: Migrations run in wrong order on prod (or run partially)

**What goes wrong:**
Someone runs migrations out of order — e.g., 020 (RLS update) before 019 (add visibility + folder), because they grabbed only "the RLS one" to re-apply. Now the `documents` table lacks the `visibility` column but has RLS policies that reference it. Every query throws `column "visibility" does not exist`.

**Why it happens:**
- 25 migration files, many interdependent. `migration 019_add_visibility_and_folder.sql` is a precondition for `020_update_rls_policies.sql` and `021_update_search_rpcs.sql`.
- Dev used Supabase Studio directly for some earlier migrations; prod needs them all applied programmatically and in order.
- A `run_all_module2.sql` exists — ambiguous whether it's idempotent or re-runnable.

**How to avoid:**
- Use `supabase db push` or `supabase migration up` against the prod project, with the migrations directory as source of truth.
- Before deploy, run `supabase db diff` against prod to confirm no drift.
- Verify ordering: migrations are numbered; `ls supabase/migrations/*.sql | sort` should produce the correct execution order. Check `run_all_module2.sql` and either delete it or confirm it's not re-applied on top.
- Write a one-off verification SQL: checks all expected columns exist in `documents`, `document_chunks`, `folders`, `threads`, `messages`, `users`. Fail loudly on mismatch.

**Warning signs:**
- `relation "folders" does not exist` or `column "visibility" does not exist` in Fly logs.
- Ingestion fails with schema errors.
- RLS allows or blocks the wrong rows.

**Phase to address:** P3 (migration runner + post-migration schema check)

---

### Pitfall 12: Supabase Storage bucket + policies not created in prod

**What goes wrong:**
Migrations create the `documents` bucket via SQL (`007_create_storage_bucket.sql`), but storage policies are managed separately (either in SQL via `storage.objects` policies or in the dashboard). If `storage.objects` policies aren't applied to prod, uploads either fail with "row violates row-level security" or worse, succeed but let any user download any other user's originals.

**Why it happens:**
- Storage policies live in the `storage.objects` table, which Supabase Studio shows under a separate "Storage" UI — easy to miss when copying "Database" migrations.
- The bucket itself may or may not be public — a dev-friendly "public bucket" setting in dev might be different in prod.

**How to avoid:**
- In P3, after migrations, verify:
  1. `SELECT id, name, public FROM storage.buckets WHERE name = 'documents'` — expect the right `public` flag.
  2. `SELECT policyname, qual, with_check FROM pg_policies WHERE tablename = 'objects' AND schemaname = 'storage'` — expect user-scoped policies for `documents` bucket.
- If policies live in migration SQL, great — confirm they're in the migrations dir. If they live only in Studio, export them as SQL and add to migrations (reproducibility).
- Smoke test: sign in as user A, upload file, get storage URL. Sign in as user B, attempt to fetch user A's URL — must 403.

**Warning signs:**
- Uploads fail with `new row violates row-level security policy for table "objects"`.
- Signed URLs return 403 even for the owning user.
- User B can fetch user A's original PDFs.

**Phase to address:** P3 (storage bucket + policy verification + cross-user test)

---

### Pitfall 13: No rate limiting on `/api/chat` — scraper drains the LLM budget overnight

**What goes wrong:**
A bot finds the public chat endpoint, scripts 10k requests, and by morning the OpenRouter/OpenAI account is out of credits. Or a single bad actor authenticated with the demo account (`ragtest1`) loops the tool-use agent to rack up charges.

**Why it happens:**
- No rate limiting currently in `backend/main.py` or any router.
- Demo credentials are documented in `CLAUDE.md` and will be in README — shared wide.
- The agentic tool loop can multiply a single request into many LLM calls (retrieval + rerank + answer + optional subagent); one bad request is expensive.

**How to avoid:**
- Add per-IP rate limit on `/api/chat` (e.g., `slowapi` or simple in-memory token bucket) — target 10 req/min per IP, 100/day per user.
- Add per-user daily cap on total LLM spend — track tokens per user_id per day in a new `usage_daily` table, reject over threshold.
- Cap tool-loop iterations (already constrained for explorer at `explorer_max_iterations=6`, but verify main chat loop has similar). Check `routers/chat.py` while-loop has a max-iterations break.
- Put LLM API key in Fly secrets with a dollar-limit set at the provider (OpenRouter has org-level limits; OpenAI has usage caps). Belt + suspenders.
- Use an OpenRouter key that's distinct from personal/dev, with a low monthly cap for this demo.

**Warning signs:**
- LangSmith traces spike overnight.
- OpenRouter dashboard shows unusual model calls from a single IP.
- Fly logs show sustained POST /api/chat traffic without corresponding user activity.

**Phase to address:** P7 (rate limit + provider-level cap + usage tracking)

---

### Pitfall 14: LangSmith free tier flooded with noisy traces

**What goes wrong:**
Every chat request + every tool call + every sub-agent invocation creates LangSmith traces. Free tier (5k traces/month as of 2026 — confirm current limits) hits the cap within days of demo traffic, traces stop recording, observability goes dark right when you need it for debugging prod.

**Why it happens:**
- `setup_tracing()` in `main.py` is unconditional — traces every request, including health checks if they're wrapped.
- `langchain_project: "rag-masterclass"` reuses the dev project — dev noise commingles with prod.
- The tool-use loop produces many child runs per request, each a trace.

**How to avoid:**
- Create a distinct LangSmith project: `langchain_project = "rag-masterclass-prod"`. Set via Fly secret.
- Sample traces: only enable `LANGCHAIN_TRACING_V2=true` for a percentage of requests, or disable for health check paths. `langsmith` SDK supports `@traceable(run_type=..., sample_rate=...)`.
- Add a kill switch: env var `LANGSMITH_ENABLED=false` that short-circuits `setup_tracing()`. Flip it off in a pinch without redeploying.
- Use LangSmith dashboard to set up alerts at 75% of quota.

**Warning signs:**
- LangSmith dashboard shows "quota exceeded" banner.
- New traces stop appearing mid-session.
- Dev and prod traces intermixed in the same project.

**Phase to address:** P7 (LangSmith prod project + sampling/kill switch)

---

### Pitfall 15: Timezone assumptions break when Fly host runs UTC

**What goes wrong:**
Dev machine is local TZ (e.g., America/Los_Angeles). Fly containers default to UTC. Code that uses `datetime.now()` without tz, or formats timestamps without timezone, silently shows times 7–8 hours off in the UI, or sorts messages wrong, or expires tokens at the wrong moment.

**Why it happens:**
- `datetime.now()` without `tz=timezone.utc` returns naive local time.
- Supabase stores `timestamptz` correctly, but Python code comparing retrieved rows to `datetime.now()` (naive) will error or give wrong results.
- JWT expiry comparisons assume UTC; a naive datetime comparison can skew by hours.

**How to avoid:**
- Audit backend for `datetime.now()` without `tz=` — grep for `datetime.now()` and `datetime.utcnow()` (deprecated in 3.12+). Replace with `datetime.now(timezone.utc)`.
- Set `TZ=UTC` explicitly in Dockerfile (`ENV TZ=UTC`) so behavior is predictable even if a base image changes.
- Frontend converts to user's local TZ for display only — backend stays in UTC.
- Test: create a thread at 11pm Pacific, confirm the `created_at` is stored in UTC and renders correctly as "11pm PT" in the UI, not "6am next day."

**Warning signs:**
- Thread timestamps in the UI are 7–12 hours off.
- JWT verification fails unpredictably ("token expired" when it shouldn't be).
- Sorts by `created_at` flip order compared to local dev.

**Phase to address:** P2 (Dockerfile TZ=UTC), P4 (post-deploy timestamp smoke test)

---

### Pitfall 16: SSE + CORS preflight edge cases (Accept: text/event-stream + credentials)

**What goes wrong:**
Frontend uses `fetch` (not `EventSource`) for SSE because the auth flow needs `Authorization` header (EventSource doesn't support custom headers). `fetch` with non-simple headers triggers a preflight OPTIONS. If the preflight's `Access-Control-Allow-Headers` doesn't include `Authorization` and `Content-Type`, the actual POST never happens. Chat silently fails on the Vercel origin.

**Why it happens:**
- EventSource limitation → fetch+ReadableStream pattern is standard for authed SSE.
- `Authorization`, `Content-Type: application/json`, and sometimes `Accept: text/event-stream` all make the request "non-simple" → preflight required.
- Current CORS config uses `allow_headers=["*"]` which *should* work, but some combinations of `allow_credentials=True` + wildcard headers are also spec-invalid.

**How to avoid:**
- Confirm `allow_credentials=False` (from Pitfall 7) — then `allow_headers=["*"]` is valid.
- If `allow_credentials` must be True (future cookie auth), switch to explicit `allow_headers=["Authorization","Content-Type","Accept"]`.
- Test preflight explicitly: `curl -X OPTIONS https://<fly>/api/chat/... -H "Origin: https://<vercel>" -H "Access-Control-Request-Method: POST" -H "Access-Control-Request-Headers: authorization,content-type" -i`. Expect 200 + appropriate `Access-Control-Allow-*` headers.

**Warning signs:**
- Chat button click shows OPTIONS 200 then nothing in Network tab.
- Browser console: `Request header field authorization is not allowed by Access-Control-Allow-Headers in preflight response`.

**Phase to address:** P6 (CORS hardening + preflight curl test)

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Using a single `.env` at repo root for both frontend + backend | Works across workspaces | Can't tell which vars are safe to expose; `VITE_*` leakage risk | Dev only — prod must split (Fly secrets vs Vercel env) |
| `allow_origins=["*"]` in dev | No CORS friction locally | Invalid + broken with credentials in prod | Dev only — must be explicit allowlist in prod |
| `min_machines_running = 0` (Fly free tier) | $0/month | Cold starts break first-use demos | Demo never | Acceptable for cost-sensitive side projects, with UX for "server waking" |
| Running migrations via Supabase Studio paste-and-run | Visual, forgiving | Order drift, untracked changes between dev and prod | Never for prod — always `supabase db push` |
| Keeping `docling` unpinned | Gets latest features | Reproducibility broken; image size changes silently | Never in prod — pin before P2 |
| Using demo `ragtest1@gmail.com` creds as public login | Easy portfolio demo | Shared account = rate limit / abuse vector | Acceptable if combined with per-IP rate limiting |
| No rate limiting | Ship faster | LLM budget drain by a single scraper | Never for public-exposed LLM endpoints |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Fly.io ↔ FastAPI | Using `127.0.0.1` as host — Fly health checks fail | Bind to `0.0.0.0` in uvicorn command; Fly injects `PORT` env var — respect it |
| Fly.io ↔ SSE | Relying on default idle timeouts | Configure `[[services]] grace_period`, `soft_limit`, send keep-alive SSE comments every 15s |
| Vercel ↔ SPA routing | 404 on deep-linked routes (e.g., `/documents`) | Add `vercel.json` rewrite: `{ "source": "/(.*)", "destination": "/index.html" }` |
| Vercel ↔ Fly (API) | Proxying SSE through Vercel rewrites | Call Fly directly via `VITE_API_BASE_URL`; don't rewrite `/api/*` |
| Supabase prod ↔ Migrations | Hand-editing Studio and calling it done | `supabase db push` from CLI; commit migrations; verify with `supabase db diff` |
| Supabase Auth ↔ Frontend | `Site URL` left at localhost | Update Site URL + Redirect URLs after Vercel domain is known |
| OpenRouter ↔ Embeddings | Using the same base URL for chat and embeddings | Keep embeddings pointed at OpenAI (`embedding_base_url`) — OpenRouter doesn't guarantee embedding endpoints |
| Supabase Storage ↔ RLS | Creating bucket in dashboard, skipping policies | Create bucket + policies in migration SQL; verify `storage.objects` policies exist |
| Supabase Realtime ↔ Fly cold start | Ingestion status channel dies during cold start | Client-side reconnect with backoff; or use polling fallback after N failed realtime reconnects |
| LangSmith ↔ SDK | Tracing enabled by default → quota exhaustion | Separate prod project, sample rate, kill switch env var |
| Docling ↔ Alpine/slim images | Missing libGL, libmagic, tesseract at runtime | Use Debian slim + install native deps; smoke test with real files |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Fly auto-stop cold start on every demo visit | 5–30s first-load latency | `min_machines_running = 1` for demo, warmup ping on frontend mount | Any traffic pattern with gaps > idle timeout |
| Docling model load on first request | First ingestion takes 30s+ | Pre-warm by importing in `main.py` startup | Any cold start touching parsing_service |
| LLM tool loop without cap | Runaway agent iterations cost $ and time | Enforce max_iterations in main chat loop (explorer already has this) | A single malicious or broken query |
| Embedding every chunk on re-upload | Slow re-uploads, duplicate embedding cost | `record_manager.py` diffs chunks by hash — ensure it's active in prod path | Once library has >100 docs being re-uploaded |
| SSE without keep-alive comments | Proxies close idle connections mid-stream | Send `: keepalive\n\n` every 15s during long LLM calls | LLM takes >30s to produce first token |
| No pagination on `/api/documents` | Page load grinds when user has 500+ docs | Already in DB but verify API has limit+offset | ~200+ docs |
| Supabase Realtime subscribing to all rows | Traffic scales with total users, not just user's docs | Filter subscription to `user_id=eq.<current>` | 10+ concurrent users |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Service role key in frontend bundle | Full DB access for any visitor | CI grep guard in `frontend/`; Pitfall 2 |
| `.env` in Docker image | Secrets in public registry | `.dockerignore`; Pitfall 3 |
| `allow_origins=["*"]` in prod | Any site can make authed requests | Explicit allowlist; Pitfall 7 |
| No rate limit on LLM endpoint | Budget drain + DoS | Per-IP rate limit + per-user daily cap; Pitfall 13 |
| Demo credentials with no per-account cap | Abuse via shared demo login | Daily token cap per user_id; provider-level cap |
| JWT verification skipped on any endpoint | RLS assumes user context | Audit all routers require `Depends(get_user_id)` — spot check for any endpoint without it |
| Unsigned Supabase Storage URLs for private docs | Anyone with URL can download | Use signed URLs with short expiry for private docs; never return raw public URLs |
| Logging user queries with PII to LangSmith | Data exposure if LangSmith leaks | Review what's traced; consider redaction for prompt content |
| `execute_readonly_query` RPC exposing schema | Attacker enumerates tables via text-to-SQL tool | Verify RPC blocks dangerous keywords (migration 015 claims this — audit) |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Cold-start hang with no feedback | User thinks app is broken, bounces | "Server waking up (~15s)..." state after 3s of no response |
| Silent CORS failure | Chat button does nothing, no error message | Catch `TypeError: Failed to fetch`, show explicit "Connection issue" banner |
| Email verification link broken | User can't complete signup | Dry-run signup flow before demo; keep "Resend verification" accessible |
| Realtime disconnect during upload | Status frozen at "Processing" forever | Polling fallback: after 3 missed realtime events, poll `/api/documents/:id` every 5s |
| Vercel SPA deep link 404 | Shared link to `/documents` returns Vercel 404 | `vercel.json` SPA rewrite |
| Demo credentials already "in use" elsewhere | Two visitors interfere with each other's data | Seed defaults + instruct visitors to sign up with their own email (rate-limited) OR wipe demo account on a cron |

## "Looks Done But Isn't" Checklist

- [ ] **Dockerfile:** Builds locally — but also verify `docker run` starts the server, `/api/health` is 200, AND a real PDF uploads + gets parsed inside the container. Docling system-lib failures don't show up in health checks.
- [ ] **CORS:** Local dev works — but test from the deployed Vercel origin, not localhost, and run a preflight OPTIONS curl.
- [ ] **Secrets:** Fly secrets set — but also grep the image (`docker history`, `docker run ... env`) and the frontend bundle for secret-shaped strings.
- [ ] **Migrations:** Applied — but verify each extension (`vector`, `ltree`, `pg_trgm`) exists AND run a search query end-to-end.
- [ ] **Storage:** Bucket created — but verify policies in `pg_policies WHERE schemaname='storage'` AND cross-user access test.
- [ ] **Auth:** Login works — but complete a fresh signup + email verification flow on the prod URL, not just "sign in with existing account."
- [ ] **SSE:** Streams in dev — but `curl -N` against prod URL and confirm tokens arrive incrementally, not as one burst.
- [ ] **Rate limit:** Added — but script 100 requests in a loop against `/api/chat` and confirm you get 429s.
- [ ] **Realtime:** Subscribes — but simulate a cold-start disconnect (kill and restart Fly machine mid-upload) and verify UI recovers.
- [ ] **Observability:** LangSmith traces appearing — but confirm the `langchain_project` is the prod project, not dev, AND that noise traces (health checks) are excluded.
- [ ] **Demo walk-through:** You've used it — but have a non-developer friend do the signup + chat + upload flow from a phone with no coaching.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Secret committed to git | HIGH | Rotate the secret at the provider immediately; `git filter-repo` or BFG to purge from history; force-push; notify any collaborators. Cost scales with how public the repo is. |
| Service role key in frontend bundle | HIGH | Rotate service role key in Supabase (Project Settings → API → Reset); redeploy backend + frontend; audit logs for suspicious writes during exposure window |
| Docker image bloat | LOW | Refactor Dockerfile to multi-stage; tighter `.dockerignore`; redeploy |
| Docling runtime missing libs | LOW | Add `apt-get install` line; redeploy; no data loss |
| CORS misconfig | LOW | Update `CORS_ORIGINS` env var; redeploy backend; no data impact |
| SSE buffering | MEDIUM | Diagnose proxy layer; add `X-Accel-Buffering: no`; switch Vercel rewrite → direct origin; may require small frontend change |
| Auth redirect URLs wrong | LOW | Update in Supabase dashboard; no redeploy needed; existing un-verified users may need manual re-verification email |
| Migrations out of order | MEDIUM-HIGH | If data already written: may need a new migration to fix drift. If empty: drop prod DB and re-run from scratch — only possible before users exist |
| LLM budget drained | MEDIUM | Add rate limiting retroactively; rotate API key if compromised; top up provider; communicate outage |
| Cold start breaking demo | LOW | Bump `min_machines_running` to 1; add frontend warmup ping |
| LangSmith quota exhausted | LOW | Flip kill-switch env var; reduce sampling; wait for monthly reset or upgrade |
| Timezone bugs in stored data | HIGH | If `timestamptz` used in Supabase, data is correct — only display logic needs fixing. If naive datetimes stored, may need backfill migration |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. VITE_* secret leakage | P1 (define allowlist), P5 (Vercel env), P8 | Grep built bundle for secret prefixes |
| 2. Service role in frontend | P1 (CI guard), P6, P8 | CI fails on `service_role` in `frontend/`; RLS smoke test |
| 3. `.env` leaks into image/git | P1 | `.dockerignore` exists; `git log -- .env` empty; `docker run` env inspection |
| 4. Docker image bloat | P2 | `docker images` < 2 GB; build time < 5 min |
| 5. Docling missing system libs | P2, P8 | Real PDF + image + XLSX upload succeeds in container |
| 6. Fly cold start kills SSE | P4, P6 | First request after 10 min idle completes within 20s OR warmup path confirmed |
| 7. CORS wildcard + credentials | P6 | Explicit origin in preflight response; `curl -i OPTIONS` check |
| 8. SSE proxy buffering | P5, P6 | `curl -N` shows incremental tokens in prod |
| 9. Auth redirect URLs stale | P3, P8 | Fresh signup + email verification E2E passes |
| 10. pgvector/ltree extensions | P3, P8 | `pg_extension` query confirms all 3; search E2E returns results |
| 11. Migrations out of order | P3 | `supabase db diff` clean; schema verification query passes |
| 12. Storage policies missing | P3 | `pg_policies` query confirms; cross-user access test 403s |
| 13. No rate limit / LLM drain | P7 | 100-req loop returns 429s; provider-level cap set |
| 14. LangSmith noise flood | P7 | Prod project distinct; sampling configured; kill switch tested |
| 15. Timezone bugs | P2 (TZ=UTC), P4 | UI timestamps match expected local TZ rendering |
| 16. SSE + CORS preflight | P6 | Authenticated SSE request from Vercel origin completes end-to-end |

## Sources

- Current repo code: `backend/main.py` (CORS config with `allow_origins=["*"]` + `allow_credentials=True` — confirmed invalid per MDN CORS spec), `backend/config.py` (single `.env` pattern), `backend/requirements.txt` (`docling` unpinned).
- Migration file listing confirms extension + RLS ordering dependencies.
- MDN / Fetch spec on CORS credentials + wildcard origin incompatibility (HIGH confidence — long-standing browser spec).
- Fly.io docs on auto-stop machines and SSE / streaming proxy behavior (MEDIUM — platform-specific, verify current free-tier limits at deploy time).
- Vercel docs on SPA rewrites and streaming through rewrites (MEDIUM — Vercel's edge streaming support has evolved; confirm current behavior for Node/SSE from external origins before finalizing P5).
- Supabase docs on Auth redirect URL configuration and Storage RLS policies (HIGH — well-documented).
- Docling GitHub issues on system library requirements for PDF/OCR paths (MEDIUM — verify current docling version's dep list at pin time).
- LangSmith pricing page for current free-tier trace quota (LOW — confirm current limits at deploy time; quota numbers change).

---
*Pitfalls research for: v1.1 Portfolio Deployment*
*Researched: 2026-04-22*
