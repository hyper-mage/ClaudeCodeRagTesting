# Board Game Knowledge Base RAG

## What This Is

An agentic RAG application specialized for board games. It combines a pre-seeded default knowledge base of popular board games with user-uploaded private collections, providing intelligent chat that can search, compare, and recommend across the entire library. The agent uses Claude Code-inspired tooling (ls, tree, grep, glob, read) with transparent tool calls to navigate a hierarchical folder-based knowledge base stored in Supabase. Users bring their own OpenRouter key via one-click OAuth (BYOK) and chat on any model they choose, with per-message cost visibility; a flag-gated, cost-bounded owner-key demo fallback keeps the public demo alive for keyless visitors.

## Core Value

The agent can intelligently search and reason across a structured board game knowledge base — finding rules, comparing mechanics, and recommending games — using the right tool for the job, transparently.

## Current Milestone: v1.3 Web Search & Agent Personas

**Goal:** Restore the web search tool and let users switch the chat agent persona (board-game expert ↔ general assistant), both retaining full tool access.

**Target features:**
- Fix/restore the web search tool (Tavily Bearer-auth update, ensure the tool surfaces when configured, prod-verify)
- Predefined agent personas — a curated set including the current expert plus a vanilla general assistant, all tool-enabled
- Per-thread persona pin + user-level default persona (mirrors the v1.2 model-pin infrastructure)
- Persona picker UI + settings-page default (mirrors the model picker)

## Requirements

### Validated

- ✓ User authentication with email/password via Supabase Auth — Module 1
- ✓ Chat with SSE streaming and stateless completions — Modules 1-2
- ✓ Thread management (create, list, switch) — Module 1
- ✓ Document upload with processing pipeline — Module 2
- ✓ Vector search (pgvector embeddings) — Module 2
- ✓ Realtime ingestion status updates via Supabase Realtime — Module 2
- ✓ Content-addressed deduplication and incremental updates — Module 3
- ✓ LLM-powered metadata extraction on ingestion — Module 4
- ✓ Multi-format document support via Docling (PDF, DOCX, HTML, MD, TXT) — Module 5
- ✓ Hybrid search with RRF fusion (vector + keyword) — Module 6
- ✓ LLM and API reranking — Module 6
- ✓ Text-to-SQL for document metadata queries — Module 7
- ✓ Web search via Tavily — Module 7
- ✓ Tool event streaming with frontend indicators — Module 7
- ✓ Sub-agent for full-document analysis — Module 8
- ✓ Markdown rendering with attribution in chat — Module 7
- ✓ RLS on all tables (users only see their own data) — Module 2
- ✓ LangSmith observability — Module 1
- ✓ Default board game knowledge base (10 popular games, pre-seeded) — Validated in Phase 2
- ✓ Image ingestion with OCR (game board photos, rule cards) — Validated in Phase 2
- ✓ XLSX ingestion support (score sheets, game trackers) — Validated in Phase 2
- ✓ Mixed-visibility RLS (public default KB + private user docs) — Validated in Phase 1
- ✓ Explorer sub-agent for deep KB traversal and analysis — Validated in Phase 5
- ✓ Explorer sub-agent: folder summarization — Validated in Phase 5
- ✓ Explorer sub-agent: cross-reference discovery (games with similar mechanics) — Validated in Phase 5
- ✓ Explorer sub-agent: game recommendations based on context — Validated in Phase 5
- ✓ Explorer sub-agent: streaming progress in chat UI — Validated in Phase 5
- ✓ Explorer budget enforcement (iterations, tool calls, summary chars) — Validated in Phase 5
- ✓ Context-aware source selection (agent decides default KB vs private docs vs both) — Validated in Phase 6
- ✓ Smart chunking with automatic token budget management — Validated in Phase 6
- ✓ User-controllable search scope (narrow to specific folders/games) — Validated in Phase 6
- ✓ Update existing sub-agent system for consistency with new explorer agent — Validated in Phase 6

- ✓ Context-aware source selection (agent decides default KB vs private docs vs both) — v1.0 (Phase 6)
- ✓ File manager-style folder/subfolder UI for organizing documents — v1.0 (Phase 4)
- ✓ Hierarchical folder structure in Supabase storage and DB — v1.0 (Phase 1 schema + Phase 4 UI)
- ✓ KB navigation tools: ls, tree, grep, glob, read — v1.0 (Phase 3)
- ✓ Transparent tool calls in chat UI (like Claude Code) — v1.0 (Phase 3 ToolCallCard)
- ✓ Smart chunking with automatic token budget management — v1.0 (Phase 6 TokenBudget)
- ✓ User-controllable search scope (narrow to specific folders/games) — v1.0 (Phase 6 scope parsing + badge)
- ✓ Update existing sub-agent system for consistency with new explorer agent — v1.0 (Phase 6 analyze_document alignment)
- ✓ Frontend deployed to Cloudflare Pages with prod API base URL — Validated in v1.1 Phase 5 (https://boardgame-rag-prod.pages.dev)

**v1.1 Portfolio Deployment (shipped 2026-05-20 — 23/23 requirements):**

- ✓ Backend containerized — repo-root Docker image, FastAPI + Docling + native deps — v1.1 (Phase 2)
- ✓ Backend deployed to Fly.io, public `*.fly.dev` URL serving `/api/health` + SSE chat — v1.1 (Phase 4)
- ✓ Dedicated prod Supabase project — migrations, pgvector, RLS, Storage, default KB seeded — v1.1 (Phase 3)
- ✓ Auth redirect URLs + env-driven CORS allowlist hardened for prod origin — v1.1 (Phases 1, 6)
- ✓ Per-user chat rate limit + agentic tool-loop max-iterations cap — v1.1 (Phase 6)
- ✓ Secrets in Fly/CF env stores; zero secrets in image or frontend bundle — v1.1 (Phases 1, 4)
- ✓ Observability baseline — Sentry (source maps + PII scrub), prod LangSmith project, UptimeRobot monitors, DB-probing `/api/health` — v1.1 (Phase 7)
- ✓ Mobile-responsive chat — hamburger drawer + mobile shell primitives — v1.1 (Phase 6.1)
- ✓ One-click Try-demo anon onboarding + graceful chat error/retry UX — v1.1 (Phase 8)
- ✓ Portfolio README + architecture diagram + screenshots + hero GIF + shields.io badges — v1.1 (Phase 8)

**v1.2 User Options & BYOK (shipped 2026-07-11 — 26/26 requirements):**

- ✓ OpenRouter OAuth (PKCE) connect — auto-provisioned user key, no manual paste — v1.2 (Phase 10)
- ✓ Encrypted server-side key storage (MultiFernet + rotation), RLS-scoped, never returned to frontend — v1.2 (Phase 9)
- ✓ Text-to-SQL lockdown of the user-keys table (REVOKE + RPC allowlist) — v1.2 (Phase 9)
- ✓ Per-request key + model resolution — fresh client per call, no cross-user bleed — v1.2 (Phase 11)
- ✓ Secret custody: keys never in LangSmith/Sentry/logs/SSE — prod-verified live gates — v1.2 (Phase 11)
- ✓ Fail-closed keyless refuse with connect prompt when demo is off — v1.2 (Phase 11)
- ✓ Model catalog: cached OpenRouter list, free/paid tags, popular marks, price + context hints — v1.2 (Phase 12)
- ✓ Lazy TTL model-list refresh (24h, serve-stale-on-failure, never-empty) — v1.2 (Phase 12)
- ✓ Default model + per-thread model pin (persisted, free-guarded deprecated-pin fallback) — v1.2 (Phase 13)
- ✓ Theme toggle light/dark, persisted per user — v1.2 (Phase 13)
- ✓ Usage/cost: per-message cost, account balance + low-balance warning, per-thread totals — v1.2 (Phase 14)
- ✓ Settings/account page (key status masked, disconnect/reconnect, default model) — v1.2 (Phases 10/14)
- ✓ Key-gated model selection → OAuth connect flow, searchable picker with favorites — v1.2 (Phase 15)
- ✓ Owner-key demo fallback: global flag default-OFF, $0 structural cost bound live-trip-tested, non-dismissible banner — v1.2 (Phases 15/999.2)
- ✓ Chat empty-state prompts + auto-create-thread-on-send — v1.2 (Phase 999.1)

### Active

**v1.3 Web Search & Agent Personas (scoping — REQ-IDs in REQUIREMENTS.md):**

- ~~Web search tool restored and prod-verified (Tavily current auth)~~ ✓ Validated in Phase 16 (2026-07-12)
- Predefined agent personas (expert + general assistant, tool-enabled)
- Per-thread persona pin + user-level default persona
- Persona picker UI + settings-page default

### Out of Scope

- Automated ingestion pipelines or connectors — manual upload only (project constraint)
- LangChain/LangGraph — raw SDK calls only (project constraint)
- Admin UI for managing default KB — seed script or pre-deploy only
- Social features (sharing collections, public reviews) — not part of this milestone
- Mobile app — web-only for now
- Game state tracking or scoring — this is a knowledge base, not a game manager

## Context

**Existing Codebase:** 8 modules complete. Full agentic RAG pipeline operational with tool-use loop, hybrid search, sub-agents, and multi-format ingestion. Built with React+Vite frontend, Python FastAPI backend, Supabase for everything (DB, auth, storage, realtime).

**Board Game Focus:** The app is pivoting from a generic RAG tool to a board game knowledge base. The default KB provides immediate value (users can ask about popular games without uploading anything), while private uploads let enthusiasts add their own collection.

**Claude Code Inspiration:** The agent tooling mirrors Claude Code's approach — multiple specialized tools (ls, tree, grep, glob, read) that the agent selects based on the task. Tool calls are shown transparently in the UI. An explorer sub-agent handles complex multi-step searches.

**Context Window Concern:** Board game manuals can be lengthy. Smart chunking and user-controllable scope are essential to prevent the KB from consuming the entire context window. The agent must be efficient about what it pulls in.

**Storage Architecture:** All documents live in Supabase (Storage buckets for originals, `document_chunks` table for processed text). Folder hierarchy must be represented in both storage paths and DB records. Tools query the DB, not the filesystem.

## Constraints

- **Tech Stack**: React+Vite+Tailwind frontend, Python+FastAPI backend, Supabase — established, no changes
- **No LangChain**: Raw OpenAI SDK calls only — project rule
- **Supabase-Only Storage**: All KB tools must work against Supabase tables/storage, not local filesystem
- **Docling Required**: PDF/DOCX/XLSX extraction must go through Docling to produce searchable markdown
- **RLS Enforced**: Default KB visible to all users, private uploads scoped by user_id
- **Context Budget**: Agent must manage context window carefully — smart chunking + scope controls

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Pre-seed 10 default board games on deploy | Quick to seed, covers top classics, gives immediate value without user uploads | ✓ Phase 2 |
| Context-aware source selection (agent decides) | More natural than manual toggles — agent picks sources based on query intent | ✓ Phase 6 |
| File manager-style folder UI | Full drag-drop, tree sidebar, right-click menus — richest interaction model for organizing many files | ✓ Phase 4 |
| Transparent tool calls (like Claude Code) | Users see what the agent is doing — builds trust and understanding | ✓ Phase 3 |
| All KB tools query Supabase (not filesystem) | Documents already stored in Supabase — tools should use the same data layer | ✓ Phase 3 |
| Explorer sub-agent for deep traversal | Complex multi-step KB searches need isolated context — mirrors Claude Code's explorer agent pattern | ✓ Phase 5 |
| Smart chunking + user scope controls | Both needed — automatic budget management plus manual override for power users | ✓ Phase 6 |
| ltree for folder hierarchy | GiST-indexed, recursive queries, matches agent traversal patterns | ✓ Phase 1 |
| Mixed-visibility RLS (public default + private uploads) | Single table, single query path; `visibility='public'` + `user_id=auth.uid()` OR filter | ✓ Phase 1 |
| Retroactive verification via decimal phase (03.1) | Phase 3 shipped before VERIFICATION.md step existed — 03.1 closed gap without rework | ✓ Phase 03.1 |
| Free-tier deploy (Fly suspend, no keep-warm) | Portfolio traffic is sparse; accept cold-start cost, document one-line keep-warm toggle | ✓ v1.1 Phase 4 |
| Two Supabase projects — dev (`.env`) + prod (`.env.prod`) | Isolate prod data + keys from local dev; one env file per environment | ✓ v1.1 Phase 3 |
| Anonymous Supabase auth for Try-demo | One-click demo with no signup; 7-day cleanup sweep; `aud="authenticated"` (Supabase default) | ✓ v1.1 Phase 8 |
| Insert Phase 6.1 (mobile) mid-milestone | Always-visible sidebar broke mobile viewport — urgent fix, decimal phase kept numbering clean | ✓ v1.1 Phase 6.1 |
| OpenRouter Guardrail as cost cap | Guardrails replaced spend-alert toggle ($0.10 min threshold); live trip-test deferred to backlog 999.2 | ✓ Closed v1.2 (999.2 live trip PASSED; SEC-03 finding artifact) |
| OAuth-only BYOK posture (no manual key paste) | Manual paste doubles the failure + security surface; OpenRouter PKCE auto-provisions a scoped key | ✓ v1.2 Phase 10 |
| MultiFernet from day one for key encryption | KEY_ENCRYPTION_SECRET is a new-key-first list; rotation re-encrypts under keys[0] without a migration | ✓ v1.2 Phase 9 |
| Lazy TTL model cache, no scheduler | Fly free-tier suspend kills in-process timers; refresh-if-stale on read + deploy seed | ✓ v1.2 Phase 12 |
| Security front-loaded as release blockers; demo flag last | SQL lockdown in Phase 9, custody/isolation at the Phase 11 seam; demo flag hard-gated on the 999.2 cost-guardrail trip test | ✓ v1.2 (SEC-01 leak caught + fixed pre-close) |
| LangSmith gate at the run layer + runtime master toggle | Client-wrap-only gating leaked BYOK turns via the endpoint `@traceable`; `tracing_context` + `app_settings.langsmith_enabled` (suppress-only) close every flag state | ✓ v1.2 Phase 11 (prod-verified zero-run) |
| Per-request uncached key/model resolution | Module-level cache risks cross-user bleed; fresh resolver + fresh client per call | ✓ v1.2 Phase 11 |
| Plain-TEXT default_model, no FK to model_cache | A deprecated-but-pinned slug must persist so the at-send fallback notice can fire | ✓ v1.2 Phase 13 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
## Current State

**Shipped:** v1.2 User Options & BYOK (2026-07-11) — 9 phases (9-15 + 999.1/999.2), 43 plans, 26/26 requirements satisfied. Milestone audit passed at close (sole blocker — SEC-01 live human gates — cleared on prod 2026-07-11). Users connect their own OpenRouter key via one-click OAuth PKCE, pick any model per thread from a cached searchable catalog, and see per-message/per-thread cost; keys are encrypted at rest with prod-verified zero-leak custody, and a flag-gated, cost-bounded owner-key demo fallback keeps the public demo alive. See [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md).

**Prior:** v1.1 Portfolio Deployment (2026-05-20) — 9 phases, 28 plans, 23/23 requirements; live at **https://boardgame-rag-prod.pages.dev** (Fly.io + Cloudflare Pages + dedicated prod Supabase). See [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md). · v1.0 KB Navigation & Agentic RAG (2026-04-23) — 7 phases, 21 plans, 39/39 requirements. See [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md).

**Tech stack:** React 19 + Vite 6 + Tailwind 4 frontend (vitest + Testing Library); Python 3.11 + FastAPI backend (278 tests passing); Supabase (Postgres + pgvector + Auth + Storage + Realtime, migrations through 034); OpenRouter LLM (BYOK + owner demo key); Docling parsing; Sentry + LangSmith (run-layer gated) + UptimeRobot observability.

**Known tech debt carried into next milestone:**
- 2 non-blocking Phase 11 UAT scenarios (live 402-vs-429 SSE codes; prod SQL-flip smoke of the LangSmith toggle).
- Audit warnings W-1..W-6: dead-pin notice accumulates + not SSE-emitted (Phase 13); stale demo banner until thread switch (Phase 15); FE/BE scrub regex breadth mismatch + `budget_service` logger not directly filtered (Phase 11); no post-turn balance refresh (Phase 14).
- Phase 13 Nyquist PARTIAL — run `/gsd:validate-phase 13`; v1.1 phases 1, 3, 6, 6.1, 7, 8 also unvalidated.
- Pre-existing: `test_record_manager.py` fixture debt; `execute_readonly_query` 42501 SET LOCAL quirk (D-09-A); free-model provider 429s make live smokes flaky (D-999.1-LLM-A).
- Orphaned capability: `GET /api/models?free_only=true` has no frontend consumer.

**Current milestone:** v1.3 Web Search & Agent Personas — Phase 16 (Web Search Restoration) complete + prod-verified 2026-07-12 (4 plans; Tavily Bearer-auth transport fixed, env-configurable search depth, D-02 citations, red failed-state tool card, `tvly-` scrub; live smoke on boardgame-rag-prod v36). Phase 17 (Agent Personas) next.

---
*Last updated: 2026-07-12 — Phase 16 Web Search Restoration complete*
