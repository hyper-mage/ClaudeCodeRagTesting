# Milestones

## v1.3 Web Search & Agent Personas (Shipped: 2026-07-14)

**Phases completed:** 2 phases (16-17), 17 plans, 41 tasks
**Stats:** 89 commits (v1.2..v1.3), 91 files +10,438/−101, 2026-07-11 → 2026-07-14

**Delivered:** The agent's web search tool is restored end-to-end and prod-verified, and users can switch the chat agent's persona per-thread (board-game expert ↔ general assistant) with a user-level default — every persona keeping full tool access, resolved per request with no cross-user/thread bleed.

**Key accomplishments:**

- **Web search restored + prod-verified** — `_search_tavily` now uses header-only `Authorization: Bearer` auth (body `api_key` deleted) with an env-configurable `web_search_depth`; the system prompt encodes inline-markdown + trailing-`Sources:` citations; `tvly-` keys are scrubbed from logs. Verified live on `boardgame-rag-prod` against the owner's real Tavily key — success smoke returned a cited web-grounded answer, failure smoke (temp invalid key) showed the red failed-state card + graceful best-effort answer with no crash (WSRCH-01..04).
- **Failed-tool UX** — `ToolEvent.status` / `ToolCallCard` gained an `'error'` member; the `tool_result` SSE handler maps the backend `is_error` flag to a red `AlertTriangle` + red border, so any tool returning `{"error": ...}` is unmistakable at a glance (D-03/WSRCH-04).
- **Persona prompt composition** — split the monolithic `settings.system_prompt` into a persona-agnostic operational BASE plus a 2-entry per-persona VOICE registry (new `persona_service.py`), composed voice-first in `stream_chat_completion`. Board-game expert stays the default; General Assistant is a vanilla voice — both retain full tool access (persona-independent tools, D-04) (PERS-02/03).
- **Per-turn resolution seam, no bleed** — auth-gated `GET /api/personas` catalog (voice_block withheld, A5) + a non-cached `_resolve_persona` that resolves the voice once per turn (thread pin → user default → system default, D-09; validate-to-default, D-10; 42P01-tolerant) and threads it into the completion, leaving the model/key resolver untouched (Pitfall 8) (PERS-06).
- **Persistence** — additive-nullable migration 035 (`threads.persona` + `user_preferences.default_persona`, no backfill/FK/RLS); `exclude_unset` PATCH so persona/model never clobber each other (IDOR re-check intact); `default_persona` roundtrip in preferences; header picker restored from the thread read on reopen (PERS-04/05).
- **Gate-free persona pickers, wired live** — `PersonaSelector` (chat header) + `DefaultPersonaSelector` (settings) render a server-fetched catalog with NO key/cost gate (keyless users can pick); the header picker displays the effective active persona mirroring the backend resolver chain (gap-closure 17-12); plus a one-click Retry card on persisted `[Response interrupted]` turns (gap-closure 17-13) (PERS-01).

**Known deferred items at close:** 2 diagnosed debug sessions, both env-classified from Phase 17 UAT — `concurrent-turns-no-output` (D-17-CONC-A: pre-existing sync-OpenAI-client-on-asyncio-loop starvation under a single uvicorn worker; fix = `asyncio.to_thread` offload or `AsyncOpenAI`; not persona scope) and `retry-model-switch-fails` (D-17-MODCAT-A: `ModelSelector` offers non-tool/unfunded models → switching then retrying an always-tools turn errors; optional catalog filter). Both non-blocking; see STATE.md Deferred Items.

---

## v1.2 User Options & BYOK (Shipped: 2026-07-11)

**Phases completed:** 9 phases (9-15 + backlog 999.1, 999.2), 43 plans, ~150 tasks
**Audit:** passed at close — 26/26 requirements satisfied; sole audit blocker (SEC-01 live human gates) cleared on prod 2026-07-11 (see `milestones/v1.2-MILESTONE-AUDIT.md`)
**Stats:** 337 commits (v1.1..v1.2), app code 104 files +13,766/−539, 2026-05-20 → 2026-07-10

**Delivered:** Users run LLMs of their choice from their own OpenRouter keys — one-click OAuth PKCE connect, encrypted key custody, per-thread model choice from a cached catalog, and per-message cost visibility — while a flag-gated, cost-bounded owner-key demo fallback preserves the public demo.

**Key accomplishments:**

- **OpenRouter BYOK via OAuth PKCE** — one-click connect with no manual key paste; keys encrypted at rest (MultiFernet with rotation), RLS-scoped, never returned to the frontend; Text-to-SQL exfiltration lockdown via REVOKE + RPC table allowlist (SEC-02).
- **Per-request key + model resolution seam** — uncached resolver, fresh client per call, zero cross-user key/model bleed under concurrency (SEC-04); fail-closed keyless refuse with a typed connect prompt (DEMO-03).
- **SEC-01 secret custody, prod-verified** — LangSmith gate moved to the run layer with a runtime `app_settings` master toggle (migration 034); backend `_ScrubFilter` + SSE error scrub + frontend Sentry `sk-or-` scrub. Both mandatory live gates passed on prod 2026-07-11: BYOK turn (incl. tool call) produced zero LangSmith runs; Fly log sink key-free on a forced 401.
- **Model catalog + picker** — Supabase-cached OpenRouter catalog (lazy 24h TTL, serve-stale-on-failure, never-empty by design), searchable picker with Favorites/Popular/All sections, free/paid + per-Mtok price + context-length hints, per-thread model pin with a free-guarded deprecated-pin fallback.
- **Usage/cost surface + settings** — per-message cost from `usage.cost`, account balance with low-balance warning, per-thread running totals; settings page with key state (masked label, disconnect/reconnect), default model, and persisted light/dark theme.
- **Gated owner-key demo fallback** — global flag default-OFF, hard-gated on a live-trip-tested $0 structural cost bound (999.2 burn script + guardrail), non-dismissible demo banner; plus chat empty-state prompts and auto-create-on-send (999.1).

**Known deferred items at close:** 2 non-blocking Phase 11 UAT scenarios (live 402-vs-429 SSE codes; prod SQL-flip smoke of the LangSmith toggle — suppress-only post-CR-01); 6 audit tech-debt warnings W-1..W-6 (dead-pin notice accumulation/not SSE-emitted, stale demo banner until thread switch, FE/BE scrub regex breadth mismatch, budget_service logger not directly filtered, no post-turn balance refresh); Phase 13 Nyquist PARTIAL (`/gsd-validate-phase 13`).

---

## v1.1 Portfolio Deployment (Shipped: 2026-05-20)

**Phases completed:** 9 phases (1-8 + inserted 6.1), 28 plans, 53 tasks
**Audit:** passed — 23/23 requirements satisfied (see `milestones/v1.1-MILESTONE-AUDIT.md`)

**Delivered:** Board Game KB RAG shipped as a public portfolio piece — live at https://boardgame-rag-prod.pages.dev — running on free-tier Fly.io + Cloudflare Pages + a dedicated prod Supabase project, with auth, CORS, rate limiting, observability, and a portfolio README hardened for a shared demo URL.

**Key accomplishments:**

- **Dockerized backend** — repo-root single-stage image (FastAPI + Docling + poppler/tesseract native deps, non-root appuser, CPU-only torch, preloaded Docling models) validated by an end-to-end build/boot/ingest smoke script.
- **Prod Supabase project** — dedicated project with all migrations, pgvector, RLS policies, Storage bucket config, and the default board-game KB seeded (10 documents, 11 folders, 62 chunks) with content-hash idempotency.
- **Public deployment** — backend on Fly.io (free-tier suspend defaults), Vite SPA on Cloudflare Pages with SPA deep-link routing; public end-to-end login + SSE chat verified live.
- **Production hardening** — env-driven CORS allowlist, per-user chat rate limit, max-iterations cap on the agentic tool loop, anonymous-JWT auth, all secrets in Fly/CF env (zero secrets in image or bundle).
- **Mobile-responsive chat** (Phase 6.1) — hamburger-drawer shell with reusable mobile primitives (body-scroll-lock, swipe-to-close, focus-trapped MobileDrawer), sidebars hidden below 768px.
- **Observability baseline** — Sentry with source maps + JWT/email/UUID scrub, dedicated prod LangSmith project, two UptimeRobot monitors at 5-min interval, DB-reachability `/api/health` probe.
- **Portfolio polish** — one-click Try-demo anon onboarding, graceful chat error + retry UX, architecture diagram + 4 screenshots + hero GIF, portfolio README, live shields.io uptime + last-commit badges.

**Known deferred items at close:** Nyquist test-coverage validation incomplete (tracked tech debt — run `/gsd:validate-phase`); SEC-06 OpenRouter cost-cap live trip-test deferred to backlog `999.2`.

---

## v1.0 KB Navigation & Agentic RAG (Shipped: 2026-04-23)

**Phases completed:** 7 phases, 21 plans, 40 tasks

**Key accomplishments:**

- ltree-based folders table with system user ownership, mixed-visibility RLS, and Board Games root seed
- Visibility columns, mixed-visibility RLS policies, and visibility-aware search RPCs for shared default KB + private user docs
- Rerunnable seed script that ingests 10 board game markdown files into Supabase as public documents under per-game subfolders, with content-hash idempotency
- 5 KB navigation tools (ls, tree, read, grep, glob) with Supabase RPCs for regex search and glob matching against hierarchical folder structure
- Collapsible tool call cards replacing pill badges, with tool_start/tool_result SSE protocol and call_id correlation
- 9-tool chat loop with tool_start/tool_result SSE, persistent tool cards in DB, and tool selection guide in system prompt
- LLM timeout protection, incremental tool persistence, and AbortController cleanup to prevent stalls and lost tool cards
- Fixed root-level My Documents file resolution using is_("folder_id", "null") and wrapped all 5 KB tool calls with try/except error handling
- Retroactive 03-VERIFICATION.md (status=passed) citing file:line evidence for TOOL-01..08, REQUIREMENTS.md traceability flipped to Complete for TOOL-06/07/08, and audit cross-check confirming v1.0 milestone gaps closed.
- 1. [Rule 1 — Bug] `renderIcon` helper instead of dynamic component tag
- 1. [Rule 1 - Bug] setState-in-effect lint error in ContextMenu positioning
- 1. [Rule 1 - Bug] Root-level folder creation silently cancelled
- Signature:
- Explorer sub-agent generator (run_exploration) wired to the Phase 3 KB tools, enforcing 3-axis budget caps and producing Pydantic-validated ExplorerResult via 3-tier structured-output fallback. 17 unit tests green.
- EXPLORE_KB_TOOL wired into parent chat loop with async-bridged streaming dispatcher emitting nested SSE sub_event rows; find_similar and recommendation_seed modes verified by unit tests; 4 integration tests proving end-to-end SSE flow.
- SubEvent SSE parsing and nested ToolCallCard rendering with real-time X/10 progress indicator for explore_kb sub-agent calls
- tiktoken-backed TokenBudget class plus source routing and scope parsing heuristics -- standalone, fully tested, ready to wire into the chat loop in Plan 02.
- Wired TokenBudget, source routing, scope parsing, and sub-agent SSE alignment into the live chat event_generator; analyze_document now emits explore_kb-style sub_events and tool cards surface a colored scope badge.

---
